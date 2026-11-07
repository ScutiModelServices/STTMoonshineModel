import pytest

from engine import MoonshineEngine

PCM = b"\x01\x00" * 16000  # one second of 16 kHz mono s16le
SEGMENTS = (("Hello world.", 0.0, 1.0), ("Bye now.", 1.0, 2.0))


@pytest.fixture(autouse=True)
def _tmp_tokens_file(tmp_path, monkeypatch):
    """Keeps tokens.json and settings.json out of the repo, and a saved setting from leaking into the next test."""
    monkeypatch.setenv("SERVICE_TOKENS_FILE", str(tmp_path / "tokens.json"))


class FakeLoaded:
    """Stands in for a loaded model: answers `segments` (text, start, end) and records every call."""

    def __init__(self, source, segments=SEGMENTS, fail=None, fail_after=None):
        self.source, self.segments, self.calls = source, segments, []
        self.fail, self.fail_after, self.stopped = fail, fail_after, None

    def stream(self, pcm, language, beam_size, words, stop):
        """The segments one at a time, then the language; `fail` raises before the first, `fail_after` after that many."""
        self.calls.append({"bytes": len(pcm), "language": language, "beam_size": beam_size, "words": words})
        self.stopped = stop
        if self.fail:
            raise self.fail
        for number, (text, start, end) in enumerate(self.segments):
            if stop.is_set():
                return
            if self.fail_after is not None and number >= self.fail_after:
                raise RuntimeError("the model crashed at /secret/path")
            pieces = [{"start_s": start, "end_s": end, "text": word} for word in text.split()] if words else []
            yield "segment", {"start_s": start, "end_s": end, "text": text, "words": pieces}
        yield "done", {"language": language or "en"}


def make_engine(**options):
    """An engine whose loader builds FakeLoaded models; `engine.loads` lists the sources it was asked for."""
    loads = []
    segments = options.pop("segments", SEGMENTS)
    fail, fail_after = options.pop("fail", None), options.pop("fail_after", None)
    model = options.pop("model", "base")

    def loader(source):
        loads.append(source)
        return FakeLoaded(source, segments, fail, fail_after)

    options.setdefault("loader", loader)
    engine = MoonshineEngine(model, **options)
    engine.loads = loads
    return engine
