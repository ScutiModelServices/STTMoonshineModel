"""Pin the external Moonshine loader contract and the long-audio cutting independently of inference fakes."""

import sys
from types import ModuleType

import numpy as np

from engine import CHUNK_SAMPLES, Loaded, cuts, load


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
