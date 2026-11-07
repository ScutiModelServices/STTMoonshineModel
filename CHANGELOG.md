# Changelog

## Unreleased

- A local run now loads `.env` from the service folder at start (python-dotenv, same as the tool services); a real environment variable still wins, and Docker is unchanged because `.env` is not in the image.
- Untracked folders now start with `.` or `_`: `zip_versions/` is `_zip_versions/`. A local `voices`, `tem_code` or `zip_versions` folder from an older checkout needs renaming by hand.
- `run.bat` is now a menu (run the service, deploy, build the release ZIP) and `run.bat run|deploy|zip` skips it. `tools/deploy.bat`, `tools/make_zip.bat` and `tools/deploy.local.example.bat` are gone; the local deploy target is `tools/deploy.local.ini` (copy `tools/deploy.local.example.ini`).
- Admin page: **Connect to this service** card with the addresses other services can use (this page's address, same PC, Docker network, `host.docker.internal`) and every endpoint, each with a Copy button.
- Admin **Try it** panel: descriptor-driven public API requests, live text streams, JSON/media output, status and latency, cancellation and redacted curl. Auth choice (b): pasted public token stays in memory; normal scope, limits and caches apply. Shared `web/playground.js` is copied across all model and tool services.
- First version: Moonshine (`base`, float, ONNX) served on the CPU, with the admin page, tokens (rate limit,
  expiry), metrics, Settings card, update checks, weight downloads and answer cache shared with the other model
  services. Built from S1MiniModel.
- Audio is split into phrases at pauses of 0.5 s or more; each phrase is one segment, and finished phrases are remembered so live dictation (Scribe re-sends the growing window every second) only decodes the phrase being spoken. A phrase over 30 s is cut at its quietest point. No word timestamps.
- A phrase may say at most 6 tokens per second of its audio (the library allowed 192 whatever the length), which stops repeat loops on cut-off phrases from filling the live text with 1,000+ characters.
- `POST /v1/transcribe` takes 16 kHz mono s16le PCM as the body and `language`, `beam_size`, `word_timestamps` and
  `stream` as query options. `stream=true` sends one JSON line per segment, then `done`.
- Settings: `max_seconds`, `vad_filter`, `compute_type` (and the shared ones).
