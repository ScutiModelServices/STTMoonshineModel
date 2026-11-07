# Changelog

## Unreleased

- `SERVICE_MODELS_DIR` sets where a local (no Docker) run keeps downloaded model weights: `settings.apply_models_dir()` maps it to `HF_HOME` and `OLLAMA_MODELS` at start.
- Docs: `docs/guide-cli.md`, a PowerShell-only way to test the service.

### Breaking: common service environment variables

Service-owned environment variables now use `SERVICE_*`. Old names are no longer read.
Rename old names once in your real `.env`, Compose `environment:` block, and CI/secret settings.

| Old name | New name |
|---|---|
| `MOONSHINE_ADMIN_PASSWORD` | `SERVICE_ADMIN_PASSWORD` |
| `MOONSHINE_CACHE_SIZE` | `SERVICE_CACHE_SIZE` |
| `MOONSHINE_COMPUTE_TYPE` | `SERVICE_COMPUTE_TYPE` |
| `MOONSHINE_HOST` | `SERVICE_HOST` |
| `MOONSHINE_MAX_INFLIGHT` | `SERVICE_MAX_INFLIGHT` |
| `MOONSHINE_MAX_SECONDS` | `SERVICE_MAX_SECONDS` |
| `MOONSHINE_MEM_LIMIT` | `SERVICE_MEM_LIMIT` |
| `MOONSHINE_MODEL` | `SERVICE_MODEL` |
| `MOONSHINE_NUM_THREAD` | `SERVICE_NUM_THREAD` |
| `MOONSHINE_PORT` | `SERVICE_PORT` |
| `MOONSHINE_REPLICAS` | `SERVICE_REPLICAS` |
| `MOONSHINE_TOKENS_FILE` | `SERVICE_TOKENS_FILE` |
| `MOONSHINE_UPDATE_CHECK_HOURS` | `SERVICE_UPDATE_CHECK_HOURS` |
| `MOONSHINE_WARM` | `SERVICE_WARM` |
| `MOONSHINE_WEB_DIR` | `SERVICE_WEB_DIR` |
| `MOONSHINE_WEIGHTS_MARKER` | `SERVICE_WEIGHTS_MARKER` |

- Move the default service port from 9240 to 29301, including API replicas and the nginx load balancer. Update any explicit old port in your real `.env`, saved tool-service `backends.json` connections, and browser or MCP client configuration once. With Compose defaults, recreate the stack to use the new host and container ports; a custom host-port override stays as configured, while container ports still change to 29301.

- Renamed `STTMoonshineModel` to `STT_Moonshine_Model`; Docker project, API image, services, load balancer and volumes now use `stt_moonshine_model` names. Callers on `citadel_core` connect to `stt_moonshine_model_lb` at the existing port.
- Docker volume migration: existing volumes with old names are orphaned; renaming does not move data. Stop the old stack before copying; never use `down -v`. The commands below assume the previous default Compose project name; substitute actual volume names if `-p` or `COMPOSE_PROJECT_NAME` overrode it.
  - `moonshine_models` → `stt_moonshine_model_models`: `docker volume inspect moonshine_models && docker volume create stt_moonshine_model_models && docker run --rm -v moonshine_models:/from:ro -v stt_moonshine_model_models:/to alpine:3.21 sh -c "cd /from && cp -a . /to/"`
  - `moonshine_tokens` → `stt_moonshine_model_data`: `docker volume inspect moonshine_tokens && docker volume create stt_moonshine_model_data && docker run --rm -v moonshine_tokens:/from:ro -v stt_moonshine_model_data:/to alpine:3.21 sh -c "cd /from && cp -a . /to/"`
- To retain an old volume instead, set its top-level volume definition to `external: true` and `name: <old-volume-name>` in a local Compose override. Rollback: stop the renamed stack, restore the previous checkout and folder name, and restart the old stack with its original volumes; copy back newer data first if the renamed stack accepted writes.

- `run.bat` loads `.env` from the service folder for a local run: it passes `--dotenv`, the service prints which variable names it loaded (never the values), and a real environment variable still wins. A plain `python src/app.py` and Docker never read `.env`.
- Untracked folders now start with `.` or `_`: `zip_versions/` is `_zip_versions/`. A local `voices`, `tem_code` or `zip_versions` folder from an older checkout needs renaming by hand.
- `run.bat` is now a menu (run the service, deploy, build the release ZIP) and `run.bat run|deploy|zip` skips it. `tools/deploy.bat`, `tools/make_zip.bat` and `tools/deploy.local.example.bat` are gone; the local deploy target is `tools/deploy.local.ini` (copy `tools/deploy.local.example.ini`).
- Admin page: **Connect to this service** card with the addresses other services can use (this page's address, same PC, Docker network, `host.docker.internal`) and every endpoint, each with a Copy button.
- Admin **Try it** panel: descriptor-driven public API requests, live text streams, JSON/media output, status and latency, cancellation and redacted curl. Auth choice (b): pasted public token stays in memory; normal scope, limits and caches apply. Shared `web/playground.js` is copied across all model and tool services.
- First version: Moonshine (`base`, float, ONNX) served on the CPU, with the admin page, tokens (rate limit,
  expiry), metrics, Settings card, update checks, weight downloads and answer cache shared with the other model
  services. Built from STC_S1Mini_Model.
- Audio is split into phrases at pauses of 0.5 s or more; each phrase is one segment, and finished phrases are remembered so live dictation (Scribe re-sends the growing window every second) only decodes the phrase being spoken. A phrase over 30 s is cut at its quietest point. No word timestamps.
- A phrase may say at most 6 tokens per second of its audio (the library allowed 192 whatever the length), which stops repeat loops on cut-off phrases from filling the live text with 1,000+ characters.
- `POST /v1/transcribe` takes 16 kHz mono s16le PCM as the body and `language`, `beam_size`, `word_timestamps` and
  `stream` as query options. `stream=true` sends one JSON line per segment, then `done`.
- Settings: `max_seconds`, `vad_filter`, `compute_type` (and the shared ones).
