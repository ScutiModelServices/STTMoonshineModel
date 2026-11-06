"""Moonshine (ONNX, CPU) run in this process: 16 kHz mono s16le PCM in, text out.

Decoding is greedy and deterministic, so every request can be kept in the answer cache. Moonshine gives no timestamps
and handles clips of a few seconds up to about 30: longer audio is cut at its quietest point near each 30 s mark and
every piece becomes one segment (`start_s`/`end_s` are the cut points, `words` is always empty).
One transcription runs at a time per replica (onnxruntime already uses every core); scale with replicas.
Changing the CPU threads reloads the model (the sessions fix their threads when built); the next call loads it.

shortcut: PCM only, ffmpeg stays with the caller; English only."""

from __future__ import annotations

import asyncio
import logging
import os
import threading
import uuid
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Iterator

REPO = "UsefulSensors/moonshine"  # tiny and base, each as `float` and `quantized`, under onnx/merged/<size>/<precision>/
DEFAULT_MODEL = "base"
MODELS = ("tiny", "base")
COMPUTE_TYPES = ("float", "quantized")
PCM_BYTES_PER_SECOND = 16000 * 2  # 16 kHz, mono, 16-bit
CHUNK_SAMPLES = 30 * 16000  # longest piece sent to the model
SEARCH_SAMPLES = 4 * 16000  # a cut is looked for in the last 4 s of a piece
WINDOW_SAMPLES = 1600  # 100 ms; the quietest window is where the cut goes
MIN_SAMPLES = 1600  # Moonshine needs at least 0.1 s

_log = logging.getLogger(__name__)


class EngineError(RuntimeError):
    """The model could not answer. `status` is the HTTP status the service maps it to."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def folder_of(model: str, compute_type: str) -> str:
    return f"onnx/merged/{model}/{compute_type}"


def cuts(audio: Any) -> Iterator[tuple[int, int]]:
    """(start, end) sample ranges of at most CHUNK_SAMPLES, each cut at the quietest 100 ms of the last 4 s."""
    import numpy as np

    start, count = 0, len(audio)
    while count - start > CHUNK_SAMPLES:
        low, high = start + CHUNK_SAMPLES - SEARCH_SAMPLES, start + CHUNK_SAMPLES
        energy = np.convolve(np.abs(audio[low:high]), np.ones(WINDOW_SAMPLES) / WINDOW_SAMPLES, "valid")
        cut = low + int(energy.argmin()) + WINDOW_SAMPLES // 2
        yield start, cut
        start = cut
    yield start, count


class Loaded:
    """A loaded Moonshine model that transcribes one clip."""

    def __init__(self, model: Any, tokenizer: Any) -> None:
        self.model, self.tokenizer = model, tokenizer

    def stream(self, pcm: bytes, language: str | None, beam_size: int, words: bool,
               stop: threading.Event) -> Iterator[tuple[str, Any]]:
        """("segment", dict) for each piece as it is decoded, then ("done", {"language"}). `beam_size` and `words` are
        accepted for the Whisper-shaped API and ignored. Setting `stop` ends it after the piece being decoded."""
        import numpy as np

        audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
        for start, end in cuts(audio):
            if stop.is_set():
                return
            if end - start < MIN_SAMPLES:
                continue
            tokens = self.model.generate(audio[None, start:end])
            text = self.tokenizer.decode_batch(tokens)[0].strip()
            yield "segment", {"start_s": round(start / 16000, 2), "end_s": round(end / 16000, 2), "text": text, "words": []}
        yield "done", {"language": "en"}


def _models_dir(model: str, compute_type: str, *, offline: bool) -> str:
    from huggingface_hub import snapshot_download

    folder = folder_of(model, compute_type)
    root = snapshot_download(repo_id=REPO, allow_patterns=[f"{folder}/*"], local_files_only=offline, token=False)
    return str(Path(root) / folder)


def load(model: str, compute_type: str, threads: int) -> Loaded:
    """Use the cached files when they are there (no network), otherwise download them. `threads` > 0 is applied to the
    onnxruntime sessions the library builds (it does not expose the option)."""
    import moonshine_onnx
    import onnxruntime

    try:
        path = _models_dir(model, compute_type, offline=True)
    except Exception:
        path = _models_dir(model, compute_type, offline=False)
    real = onnxruntime.InferenceSession

    def session(source: Any, *args: Any, **kwargs: Any) -> Any:
        if threads > 0 and "sess_options" not in kwargs and not args:
            options = onnxruntime.SessionOptions()
            options.intra_op_num_threads = threads
            kwargs["sess_options"] = options
        return real(source, *args, **kwargs)

    onnxruntime.InferenceSession = session  # only while the library builds its sessions
    try:
        built = moonshine_onnx.MoonshineOnnxModel(models_dir=path, model_name=f"moonshine/{model}")
    finally:
        onnxruntime.InferenceSession = real
    return Loaded(built, moonshine_onnx.load_tokenizer())


def _remote_sha(repo: str) -> str:
    from huggingface_hub import HfApi

    return HfApi().model_info(repo, token=False).sha


def _cached_sha(repo: str) -> str | None:
    from huggingface_hub import snapshot_download

    try:
        return Path(snapshot_download(repo_id=repo, local_files_only=True, token=False)).name  # the folder is named by commit
    except OSError:
        return None


def default_marker() -> Path:
    """File in the shared models volume whose content changes when one replica downloads new weights."""
    configured = os.environ.get("MOONSHINE_WEIGHTS_MARKER")
    return Path(configured) if configured else Path(os.environ.get("HF_HOME") or "~/.cache/huggingface").expanduser() / ".moonshine-weights-version"


class MoonshineEngine:
    """The `loader`, `remote_sha`, `cached_sha` and `download` callables are injectable for tests. `loader(model)`
    returns an object with `stream(pcm, language, beam_size, words, stop)`."""

    def __init__(self, model: str = DEFAULT_MODEL, *, compute_type: str = "float",
                 marker: Path | None = None, loader: Callable[[str], Loaded] | None = None,
                 remote_sha: Callable[[str], str] = _remote_sha, cached_sha: Callable[[str], str | None] = _cached_sha,
                 download: Callable[[str], None] | None = None) -> None:
        if model not in MODELS:
            raise ValueError(f"model must be one of {', '.join(MODELS)}, not {model!r}")
        if compute_type not in COMPUTE_TYPES:
            raise ValueError(f"compute_type must be one of {', '.join(COMPUTE_TYPES)}, not {compute_type!r}")
        self.model = model
        self.compute_type = compute_type
        self._threads: int | None = None
        self._marker = marker
        self._seen = self._read_marker()
        self._loader = loader or (lambda name: load(name, self.compute_type, self._threads or 0))
        self._remote_sha_of, self._cached_sha_of = remote_sha, cached_sha
        # the default fetches only the folder this engine loads, not every size and precision in the repository
        self._download_of = download or (lambda repo: _models_dir(self.model, self.compute_type, offline=False))
        self._base: Loaded | None = None
        self._load_lock = threading.Lock()
        self._gate = asyncio.Semaphore(1)
        self.generation = 0  # part of the answer cache key; changes whenever the loaded model is dropped

    @property
    def num_thread(self) -> int | None:
        return self._threads

    @num_thread.setter
    def num_thread(self, count: int) -> None:
        if count != self._threads:
            self._threads = count
            self._forget()  # CTranslate2 fixes its threads at build time: the next call loads the model again

    @property
    def ready(self) -> bool:
        return self._base is not None

    async def close(self) -> None:
        self._base = None

    async def warm(self) -> None:
        """Load the model now so the first request does not pay for it."""
        await asyncio.to_thread(self._base_model)

    def _base_model(self) -> Loaded:
        with self._load_lock:
            if self._base is None:
                self._base = self._loader(self.model)
            return self._base

    def _language(self, language: str) -> str | None:
        if language == "auto":
            language = ""
        if language not in ("", "en"):
            raise EngineError(f"Moonshine {self.model} only knows English, not {language!r}", 400)
        return "en"

    def _events(self, pcm: bytes, language: str, beam_size: int, words: bool, stop: threading.Event) -> Iterator[tuple[str, Any]]:
        code = self._language(language)
        try:
            yield from self._base_model().stream(pcm, code, beam_size, words, stop)
        except EngineError:
            raise
        except Exception as error:  # model errors vary and may hold paths: log them, never send them
            _log.exception("Transcription failed")
            raise EngineError("Transcription failed. Try again.", 500) from error

    @staticmethod
    def body(segments: list[dict[str, Any]], language: str, pcm: bytes) -> dict[str, Any]:
        return {"text": " ".join(s["text"] for s in segments if s["text"]), "language": language,
                "segments": [{k: s[k] for k in ("start_s", "end_s", "text")} for s in segments],
                "words": [w for s in segments for w in s["words"]],
                "duration_s": round(len(pcm) / PCM_BYTES_PER_SECOND, 2)}

    async def transcribe(self, pcm: bytes, language: str = "en", beam_size: int = 1, words: bool = True) -> dict[str, Any]:
        stop = threading.Event()
        async with self._gate:
            def run() -> dict[str, Any]:
                events = list(self._events(pcm, language, beam_size, words, stop))
                return self.body([v for k, v in events if k == "segment"], events[-1][1]["language"], pcm)

            return await asyncio.to_thread(run)

    async def transcribe_stream(self, pcm: bytes, language: str = "en", beam_size: int = 1,
                                words: bool = True) -> AsyncIterator[tuple[str, Any]]:
        """("segment", dict) pieces, then ("done", {"language"}). Holds the slot until the last piece; when the caller
        closes the iterator the transcription is stopped."""
        stop = threading.Event()
        async with self._gate:
            events = self._events(pcm, language, beam_size, words, stop)
            try:
                while (event := await asyncio.to_thread(next, events, None)) is not None:
                    yield event
            finally:
                stop.set()  # a running `next` then ends by itself; closing the generator here could race with it

    # Updates: the Hub revision of the weights, shared by all replicas through one models volume.

    async def cached_sha(self) -> str | None:
        return await asyncio.to_thread(self._cached_sha_of, REPO)

    async def remote_sha(self) -> str:
        return await asyncio.to_thread(self._remote_sha_of, REPO)

    async def pull(self) -> None:
        await asyncio.to_thread(self._download_of, REPO)

    async def unload(self) -> None:
        """Forget the loaded model here and tell the other replicas to do the same; the next call loads the new weights."""
        if self._marker is not None:
            self._marker.parent.mkdir(parents=True, exist_ok=True)
            self._seen = uuid.uuid4().hex
            self._marker.write_text(self._seen, "utf-8")
        self._forget()

    def sync(self) -> None:
        """Called every second: drop the loaded model when another replica downloaded new weights."""
        current = self._read_marker()
        if current != self._seen:
            self._seen = current
            self._forget()

    def _forget(self) -> None:
        with self._load_lock:
            self._base = None
            self.generation += 1  # kept answers are from the old weights

    def _read_marker(self) -> str | None:
        try:
            return self._marker.read_text("utf-8") if self._marker else None
        except OSError:
            return None
