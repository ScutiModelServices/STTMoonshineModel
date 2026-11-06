"""Real-model check: downloads the weights if missing, transcribes a WAV (or 3 s of noise) and prints text and timing.
Usage: uv run python tools/smoke.py [file.wav 16 kHz mono s16] [threads]"""
import asyncio
import sys
import time
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from engine import MoonshineEngine  # noqa: E402


async def main() -> None:
    engine = MoonshineEngine("base", compute_type="float")
    if len(sys.argv) > 2:
        engine.num_thread = int(sys.argv[2])
    if len(sys.argv) > 1:
        with wave.open(sys.argv[1]) as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getsampwidth()) == (16000, 1, 2), "need 16 kHz mono s16"
            pcm = wav.readframes(wav.getnframes())
    else:
        import os
        pcm = os.urandom(3 * 32000)
    t = time.perf_counter()
    await engine.warm()
    print(f"load {time.perf_counter() - t:.1f}s")
    t = time.perf_counter()
    out = await engine.transcribe(pcm)
    print(f"transcribe {time.perf_counter() - t:.1f}s for {out['duration_s']}s audio\n{out['text']!r}")


asyncio.run(main())
