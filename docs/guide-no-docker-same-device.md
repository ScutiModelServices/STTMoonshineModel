# STT_Moonshine_Model: without Docker, on Windows

Run Moonshine on the CPU directly with Python: one process, no load balancer, listening on `127.0.0.1:29301`.

## Requirements
- Windows with Python 3.11 or newer and uv (`winget install astral-sh.uv`).
- Internet on the first start (about 250 MB of weights).
- RAM for the model (one copy).

## Start
Double-click `run.bat`, or run it in a terminal from `STT_Moonshine_Model\`. Choose **1 Run the service** in the menu, or run `run.bat run` to skip the menu. It runs `uv sync` to create or update `.venv`, then starts
`python src/app.py`. The first start downloads about 250 MB of weights.

Linux or macOS:
```bash
cd STT_Moonshine_Model
uv sync
uv run python src/app.py
```

## Settings
`run.bat` loads `.env` in this folder (copy `.env.example`) through `--dotenv` and prints the names it loaded, never the values; a real environment variable wins over it. A plain `python src/app.py` does not read `.env`. Set variables in `.env` or in the environment before starting:

| Variable | Default | Effect |
|---|---|---|
| `MOONSHINE_HOST` | `127.0.0.1` | Bind address. Use `0.0.0.0` only if other devices must reach it. |
| `MOONSHINE_PORT` | `29301` | Port. |
| `MOONSHINE_ADMIN_PASSWORD` | empty | Unlocks `/admin/` and requires tokens on every call but `/health`. Empty = no auth. |
| `MOONSHINE_WARM` | `1` | Load the model at start; with `0` the first request pays the load time. |
| `MOONSHINE_NUM_THREAD` | the library decides | CPU threads. Set it to the number of **physical** cores. |

PowerShell: `$env:MOONSHINE_ADMIN_PASSWORD = "secret"; .\run.bat`
Bash: `MOONSHINE_ADMIN_PASSWORD=secret uv run python src/app.py`

## Check
```bash
curl http://127.0.0.1:29301/health
```
`ready` is `false` until the model has loaded. Then open `http://127.0.0.1:29301/admin/` (see [guide-web-ui.md](guide-web-ui.md)),
make a token, and try a call:
```bash
ffmpeg -v error -i speech.wav -f s16le -ar 16000 -ac 1 - | curl -X POST http://127.0.0.1:29301/v1/transcribe -H "X-Internal-Token: moonshine_..." --data-binary @-
```

## Stop
Ctrl+C in the terminal. Do not run this and the Docker stack together: both use port 29301.

## Tests
`uv run pytest`.
