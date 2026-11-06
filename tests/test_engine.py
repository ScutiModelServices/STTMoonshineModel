"""Pin the external Moonshine loader contract and the long-audio cutting independently of inference fakes."""

import sys
from types import ModuleType

import numpy as np

import threading

from engine import CHUNK_SAMPLES, Loaded, cuts, load, phrases


def test_load_builds_the_library_model_from_cached_weights_and_sets_threads(monkeypatch):
    built, snapshots, threads = [], [], []
    moonshine = ModuleType("moonshine_onnx")
    hub = ModuleType("huggingface_hub")
    runtime = ModuleType("onnxruntime")

    class Model:
        def __init__(self, models_dir, model_name):
            built.append(models_dir)
            runtime.InferenceSession("encoder.onnx")  # the library builds its sessions here

    runtime.SessionOptions = type("SessionOptions", (), {})
    runtime.InferenceSession = lambda source, sess_options=None: threads.append(sess_options.intra_op_num_threads)
    moonshine.MoonshineOnnxModel = Model
    moonshine.load_tokenizer = lambda: "tokenizer"
    hub.snapshot_download = lambda **options: snapshots.append(options) or "cached"
    for name, module in (("moonshine_onnx", moonshine), ("huggingface_hub", hub), ("onnxruntime", runtime)):
        monkeypatch.setitem(sys.modules, name, module)

    loaded = load("base", "float", 4)

    assert isinstance(loaded, Loaded) and loaded.tokenizer == "tokenizer"
    assert built[0].replace("\\", "/") == "cached/onnx/merged/base/float" and threads == [4]
    assert snapshots == [{"repo_id": "UsefulSensors/moonshine", "allow_patterns": ["onnx/merged/base/float/*"],
                          "local_files_only": True, "token": False}]
    assert runtime.InferenceSession.__name__ != "session"


def test_short_audio_is_one_piece():
    assert list(cuts(np.zeros(5 * 16000, np.float32))) == [(0, 5 * 16000)]


def test_long_audio_is_cut_at_its_quietest_point_and_covers_everything():
    audio = np.ones(80 * 16000, np.float32)
    quiet = CHUNK_SAMPLES - 2 * 16000  # a gap two seconds before the 30 s mark
    audio[quiet:quiet + 3200] = 0
    pieces = list(cuts(audio))
    assert quiet <= pieces[0][1] <= quiet + 3200
    assert pieces[0][0] == 0 and pieces[-1][1] == len(audio)
    assert all(a[1] == b[0] for a, b in zip(pieces, pieces[1:]))
    assert all(end - start <= CHUNK_SAMPLES for start, end in pieces)


def _talk(*bursts, gap=0.7):
    """16 kHz audio: a loud 200 Hz tone per (seconds) burst, `gap` seconds of silence between and 0.3 s at each end."""
    quiet = lambda seconds: np.zeros(int(seconds * 16000), np.float32)
    parts = [quiet(0.3)]
    for seconds in bursts:
        t = np.arange(int(seconds * 16000)) / 16000
        parts += [(0.3 * np.sin(2 * np.pi * 200 * t)).astype(np.float32), quiet(gap)]
    return np.concatenate(parts)


def test_phrases_split_at_pauses_and_the_last_is_finished_once_a_pause_follows_it():
    found = list(phrases(_talk(1.0, 2.0, 1.5)))
    assert len(found) == 3 and all(finished for *_, finished in found)
    assert [round((end - start) / 16000, 1) for start, end, _ in found] == [1.4, 2.4, 1.9]  # speech plus 0.2 s each side
    assert list(phrases(_talk(1.0, 1.0)[:int(2.5 * 16000)]))[-1][2] is False  # cut while the second one is still going


def test_a_short_pause_does_not_split_a_phrase():
    assert len(list(phrases(_talk(1.0, 1.0, gap=0.3)))) == 1


def test_very_quiet_audio_is_one_unfinished_phrase():
    assert list(phrases(np.full(32000, 0.001, np.float32))) == [(0, 32000, False)]


def test_a_finished_phrase_is_the_same_when_more_audio_follows():
    audio = _talk(1.0, 2.0, 1.5)
    full = list(phrases(audio))
    for end in (int(2.2 * 16000), int(3.0 * 16000), int(5.9 * 16000)):
        for start_s, end_s, finished in phrases(audio[:end]):
            if finished:
                assert (start_s, end_s) in [(a, b) for a, b, _ in full]


class _Counting:
    """Stands in for the Moonshine library: `generate` records the length of each audio it gets, the tokenizer says it."""

    def __init__(self):
        self.lengths = []
        self.tokenizer = self

    def generate(self, batch):
        self.lengths.append(batch.shape[1])
        return [[batch.shape[1]]]

    def decode_batch(self, tokens):
        return [f"phrase{tokens[0][0]}"]


def _text(loaded, audio):
    pcm = (audio * 32768).astype(np.int16).tobytes()
    return [v["text"] for k, v in loaded.stream(pcm, None, 1, False, threading.Event()) if k == "segment"]


def test_growing_audio_only_decodes_the_phrase_being_spoken():
    fake = _Counting()
    loaded = Loaded(fake, fake)
    audio = _talk(1.0, 2.0, 1.5)
    first = _text(loaded, audio[:int(5.0 * 16000)])  # two phrases done, the third just started
    done = len(fake.lengths)
    again = _text(loaded, audio[:int(5.0 * 16000)])  # the same audio again: finished phrases come from the memory
    assert again == first and len(fake.lengths) - done <= 1  # at most the unfinished last one
    before = len(fake.lengths)
    full = _text(loaded, audio)
    assert len(full) == 3 and full[:2] == first[:2] and len(fake.lengths) - before <= 2
