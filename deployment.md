# Deploying STTMoonshineModel

STTMoonshineModel is one HTTP service (port 9240). It runs as `moonshine` replicas behind an nginx load balancer,
`moonshine_lb`. Callers use `http://<host>:9240`; they never reach a replica directly.

## Requirements

- Docker with Compose v2.
- About 0.5 GB of RAM **per replica** for `base.en` (each replica holds the model); `small.en` needs about 1 GB.
- Network access on the first start to download the weights (about 150 MB for `base.en`) from Hugging Face.
- CPU only (onnxruntime).

## Settings

In `.env` next to `docker-compose.yml`:

| Variable | Default | Effect |
|---|---|---|
| `MOONSHINE_REPLICAS` | `1` | Number of `moonshine` containers. Read by Compose. |
| `MOONSHINE_MEM_LIMIT` | `0` (no cap) | RAM cap per container, for example `1g` (`base` float uses about 0.5 GiB; measure with `docker stats`). An out-of-memory kill then stays in the container instead of starving the host. Read by Compose. |
| `MOONSHINE_PORT` | `9240` | Host port `moonshine_lb` publishes. |
| `MOONSHINE_ADMIN_PASSWORD` | empty | Password for `/admin/`. When set, every call except `/health` must send a token as `X-Internal-Token`. Empty = no auth. |
| `MOONSHINE_NUM_THREAD` | onnxruntime decides | Starting value for the CPU threads card; a value saved on `/admin/` wins. Use the number of physical cores (`lscpu`: cores x sockets), not logical CPUs; more threads than cores slows every call. Changing it reloads the model on that replica; the next call loads it again. |

On the **Settings** card of `/admin/` (saved in `settings.json` beside the tokens, shared by all replicas; a saved
value beats the environment variable named in brackets): update check hours (`MOONSHINE_UPDATE_CHECK_HOURS`, 6),
in-flight cap (`MOONSHINE_MAX_INFLIGHT`, 0 = 4), answers kept per replica (`MOONSHINE_CACHE_SIZE`, 256, 0 = off), longest audio per call (`MOONSHINE_MAX_SECONDS`, 150, at most 900), base model
(`MOONSHINE_MODEL`, restart; `base` or `tiny`), number format (`MOONSHINE_COMPUTE_TYPE`, restart: `float` or `quantized`) and load at start (`MOONSHINE_WARM`, restart). Compose does not pass these; add the variable
under `environment:` of `moonshine` to use one as a starting value.

## Start

```bash
docker compose up -d --build
curl http://127.0.0.1:9240/health
```

Expect `"ready": true` once a replica has loaded the model. The first start downloads the weights into the `models`
volume, so `moonshine_lb` can take a few minutes to appear (the health check allows 300 s before failures count; run
`docker compose ps` and wait).

## Scaling

```bash
MOONSHINE_REPLICAS=3 docker compose up -d --build
docker compose restart moonshine_lb
```

The restart is needed because nginx resolves replica addresses once at start.

## Updating the weights

The **Updates** card compares the downloaded revision of the Hugging Face repository with its newest one. **Download
new weights** fetches it into the models volume; every replica drops its old copy within a few seconds and loads the
new one on its next request (it needs RAM for both for a moment). The download is the repository's current `main`.
Updating the service itself: `docker compose up -d --build`, then `docker compose restart moonshine_lb`.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `moonshine_lb` never starts | No replica is healthy yet (first download, or out of memory). `docker compose logs moonshine`. |
| Replicas restart in a loop | Out of RAM. Lower `MOONSHINE_REPLICAS`. |
| 401 "Invalid token" | The caller sends no token, or a revoked one. |
| 422 on `/v1/transcribe` | An empty body, an odd byte count (the body must be 16 kHz mono s16le PCM), an unknown query option, or a language other than `en` on a `.en` model. |
| 413 | The audio is longer than *Longest audio per call*. |
| 429 | Over the token's rate limit, or too many calls waiting for the model. |
| Slow answers | `base.en` runs at about 1.6x real time and `small.en` at about 0.5x on 6 cores. Use a smaller model, or set CPU threads on `/admin/` to the physical core count. |
| nginx 502 after scaling | `moonshine_lb` not restarted after the replica count changed. |

## Releasing

A plain publish (`tools\deploy.bat` option 1) only updates the `live` branch. For a release set `VERSION` (and
`pyproject.toml` to the same number), commit, then run `tools\deploy.bat` option R or
`py tools\publish_live.py --release`. `tools\make_zip.bat` then builds `zip_versions\STTMoonshineModel-<VERSION>.zip`.


## Verify with Try it

After deployment, open `/admin/` and use **Try it** with a public service token to exercise the deployed public route. It uses normal scope, admission/rate limits and cache behavior, so busy or unauthorized requests remain visible as HTTP errors. No new environment setting or admin-to-public auth bypass is introduced. Deploy the complete `web/` directory, including `playground.js`. See [the web UI guide](docs/guide-web-ui.md#try-it-send-a-real-request) for input formats, limits and token handling.
