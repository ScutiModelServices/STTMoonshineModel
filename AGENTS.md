# STTMoonshineModel

Moonshine (`useful-moonshine-onnx`, `base`, float, CPU) served over HTTP, behind the shared model-service admin page, tokens and settings. Port 9240, env prefix `MOONSHINE_`, token prefix `moonshine_`. A drop-in for `STTWhisperModel`'s `POST /v1/transcribe` shape (English only, no word timestamps); the caller decodes audio. Built from `STTWhisperModel`.

## Agent instructions
This file is the one instruction file for every coding agent; `CLAUDE.md` only imports it (`@AGENTS.md`). Edit this file, never `CLAUDE.md`.

## Commands (from this folder, venv `.venv`, managed by uv)
- Install: `uv sync` (`winget install astral-sh.uv` if uv is missing)
- Test: `uv run pytest -q` (fake model, no weights). `tests/test_admin_ui.py` needs Playwright and its browser and is skipped without it. On Windows, if uv fails with "cannot move the file to a different disk drive", set `UV_CACHE_DIR` to a folder on the same drive and `UV_LINK_MODE=copy`.
- Run: `run.bat run`, or `uv run python src/app.py` (add `--dotenv` to load `.env`), or `docker compose up -d --build`

## Rules
- Follow the `model-service-parity` skill and `AI/ModelServices/_docs/SHARED-FEATURES.md` (what must match in every model service) and `AI/ModelServices/_docs/SERVICE-SPECIFIC.md` (what differs on purpose). A change to a shared feature goes to every service; a new difference goes into `SERVICE-SPECIFIC.md` in the same change.
- `web/index.html`, `src/tokens.py`, `src/settings.py`, `src/updates.py` and `.dockerignore` are copies shared with the other model services. Change one, copy it to the others, run `python tools/check_sync.py` in each repo.
- Built from STTWhisperModel (same app shape and shared files). Differences: `POST /v1/transcribe` takes raw 16 kHz mono s16le PCM as the body (no ffmpeg here; the caller decodes) and `language`, `beam_size`, `word_timestamps`, `stream` as query options (others 422); streaming is one JSON line per segment; no `trust_remote_code`, no project models, no `temperature`/`max_tokens`; `beam_size` and `word_timestamps` are accepted and ignored (`words` is always empty); only English (`language` `en`/`auto`, else 422). Audio is split into phrases at pauses of 0.5 s or more (`engine.phrases`), one segment each; a phrase over 30 s is cut at its quietest point (`engine.cuts`); a finished phrase (pause after it) is remembered by audio hash in `Loaded._kept`, which is why live dictation stays cheap; `engine.TOKENS_PER_SECOND` caps what a phrase may say, since the library stops only at 192 tokens; `model` is `tiny` or `base`, `compute_type` is `float` or `quantized`; no `vad_filter`.
- Decoding is deterministic, so every request is cached (key = audio + options + engine generation). Model errors are logged and never sent (they can hold paths).
- Changing `num_thread` drops the loaded model: the library builds its onnxruntime sessions without a thread option, so `engine.load` swaps `onnxruntime.InferenceSession` for the duration of the build to set `intra_op_num_threads`; the next call reloads the model. This also bumps `generation`, which empties the cache.
- Weights are the Hub repo `UsefulSensors/moonshine`, folder `onnx/merged/<model>/<compute_type>`; `engine.load` uses the cached files when present and downloads only that folder otherwise. The Updates card compares the whole repository revision. The library needs `model_name` even with `models_dir`, and bundles its own tokenizer.
- Behaviour changes update `README.md`, `deployment.md`, `docs/guide-web-ui.md`, `.env.example` and `CHANGELOG.md` in the same commit.
- Never read or print `.env`, `tokens.json` or `settings.json`.
- Commit with the noreply author email `214214011+scutiii2@users.noreply.github.com` (another address is rejected on push). Push `main`, then run `python tools/publish_live.py`. Build Docker only when the Dockerfile or the dependencies changed.
