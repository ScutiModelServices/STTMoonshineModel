# STT_Moonshine_Model: Docker Desktop on this PC

Run Moonshine on the CPU in Docker Desktop on the machine you work on, so other programs on it can call it.

## Requirements

- Docker Desktop with Compose v2 (Windows: WSL2 backend).
- About 0.5 GB of RAM **per replica** for `base.en` (each replica holds the model); `small.en` needs about 1 GB. Keep `MOONSHINE_REPLICAS=1` on a PC. Docker Desktop on Windows caps its engine at about half of your RAM unless you raise it in `.wslconfig`.
- Network access on the first start to download the weights (about 150 MB for `base.en`) from Hugging Face.
- CPU only (onnxruntime).

## Steps

1. Configure. In `STT_Moonshine_Model/`:
   ```bash
   cp .env.example .env
   ```
   Set `MOONSHINE_ADMIN_PASSWORD` (empty = no auth and no admin page, fine for a local test). Leave `MOONSHINE_PORT=29301`. Leave `MOONSHINE_REPLICAS=1`.
2. Start:
   ```bash
   docker compose up -d --build
   ```
   The first start downloads about 250 MB of weights into the `stt_moonshine_model_models` volume. `stt_moonshine_model_lb` starts only after the service is healthy
   (up to 300 s grace). Watch with `docker compose ps` and `docker compose logs -f stt_moonshine_model`.
3. Check:
   ```bash
   curl http://127.0.0.1:29301/health
   ```
   `ready` is `false` until the model has loaded, then `true`.
4. Open the admin page: `http://127.0.0.1:29301/admin/` (see [guide-web-ui.md](guide-web-ui.md)) and make a token for each caller.
5. Try a call:
   ```bash
   ffmpeg -v error -i speech.wav -f s16le -ar 16000 -ac 1 - | curl -X POST http://127.0.0.1:29301/v1/transcribe -H "X-Internal-Token: moonshine_..." --data-binary @-
   ```
   Expect a JSON answer.
6. Callers connect to the published port. The caller holds the URL and token:
   - Caller on the host: `http://127.0.0.1:29301`.
   - Caller in another Docker stack on the same host: `http://host.docker.internal:29301`.

## Settings

In `.env` next to `docker-compose.yml`:

| Variable | Default | Effect |
|---|---|---|
| `MOONSHINE_REPLICAS` | `1` | Number of `stt_moonshine_model` containers. Read by Compose. |
| `MOONSHINE_MEM_LIMIT` | `0` (no cap) | RAM cap per container, for example `1g` (`base` float uses about 0.5 GiB; measure with `docker stats`). An out-of-memory kill then stays in the container instead of starving the host. Read by Compose. |
| `MOONSHINE_PORT` | `29301` | Host port `stt_moonshine_model_lb` publishes. |
| `MOONSHINE_ADMIN_PASSWORD` | empty | Password for `/admin/`. When set, every call except `/health` must send a token as `X-Internal-Token`. Empty = no auth. |
| `MOONSHINE_NUM_THREAD` | onnxruntime decides | Starting value for the CPU threads card; a value saved on `/admin/` wins. Use the number of physical cores (`lscpu`: cores x sockets), not logical CPUs; more threads than cores slows every call. Changing it reloads the model on that replica; the next call loads it again. |

On the **Settings** card of `/admin/` (saved in `settings.json` beside the tokens, shared by all replicas; a saved
value beats the environment variable named in brackets): update check hours (`MOONSHINE_UPDATE_CHECK_HOURS`, 6),
in-flight cap (`MOONSHINE_MAX_INFLIGHT`, 0 = 4), answers kept per replica (`MOONSHINE_CACHE_SIZE`, 256, 0 = off), longest audio per call (`MOONSHINE_MAX_SECONDS`, 150, at most 900), base model
(`MOONSHINE_MODEL`, restart; `base` or `tiny`), number format (`MOONSHINE_COMPUTE_TYPE`, restart: `float` or `quantized`) and load at start (`MOONSHINE_WARM`, restart). Compose does not pass these; add the variable
under `environment:` of `stt_moonshine_model` to use one as a starting value.

## Daily use

```bash
docker compose ps          # state
docker compose logs -f stt_moonshine_model
docker compose down        # stop (the weights volume is kept)
docker compose up -d --build && docker compose restart stt_moonshine_model_lb   # after a code change
```

## Problems

| Symptom | Fix |
|---|---|
| `address already in use` on 29301 | Another copy (`run.bat`, or the same stack on another compose project) is running. Stop it or change `MOONSHINE_PORT`. |
| `/health` shows `ready: false` for minutes | First start: the weights are downloading or loading. Check `docker compose logs -f stt_moonshine_model`. |
| 401 Invalid token | The caller's token is missing or revoked; make one on `/admin/`. |
| Container restarts in a loop | Out of RAM. Raise the Docker Desktop memory limit or lower the replica count. |
| `stt_moonshine_model_lb` never starts | No replica is healthy yet (first download, or out of memory). `docker compose logs stt_moonshine_model`. |
| Replicas restart in a loop | Out of RAM. Lower `MOONSHINE_REPLICAS`. |
| 422 on `/v1/transcribe` | An empty body, an odd byte count (the body must be 16 kHz mono s16le PCM), an unknown query option, or a language other than `en` on a `.en` model. |
| 413 | The audio is longer than *Longest audio per call*. |
| 429 | Over the token's rate limit, or too many calls waiting for the model. |
| Slow answers | `base.en` runs at about 1.6x real time and `small.en` at about 0.5x on 6 cores. Use a smaller model, or set CPU threads on `/admin/` to the physical core count. |
| nginx 502 after scaling | `stt_moonshine_model_lb` not restarted after the replica count changed. |

The load balancer also joins external `citadel_core` as `stt_moonshine_model_lb`. Start the Citadel stack first so that network exists; tool services on it use `http://stt_moonshine_model_lb:29301`. Docker project and API image are `stt_moonshine_model` and `stt_moonshine_model:latest`; persistent volumes have explicit `stt_moonshine_model_*` names. Volume migration and rollback instructions are in [CHANGELOG.md](../CHANGELOG.md).
