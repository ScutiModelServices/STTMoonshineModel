# STTMoonshineModel

The one place Moonshine speech-to-text is served: Useful Sensors' Moonshine (ONNX, `useful-moonshine-onnx`) with `base` by default, on the CPU.
Projects send 16 kHz mono PCM over HTTP and get text and segments back. English only, no word timestamps. It has the same admin page,
tokens, rate limits, metrics, settings and update checks as the other model services.

It is the model half of `AI/ToolServices/Scribe`: Scribe keeps ffmpeg decoding, per-user quota, the upload store and live
dictation, and calls this service for the transcription (`SCRIBE_WHISPER_URL`).

## API

| Call | Purpose |
|---|---|
| `POST /v1/transcribe` | Body: raw PCM. Query: `language`, `beam_size`, `word_timestamps`, `stream`. → `{"text", "language", "segments", "words", "duration_s", "model", "duration_ms"}`. |
| `GET /health` | `{"status": "ok", "model", "ready", "num_thread"}`; `ready` is true once the model is loaded. No token needed. |

**Input.** The body is 16 kHz, mono, signed 16-bit little-endian PCM (`application/octet-stream`), what
`ffmpeg -f s16le -ar 16000 -ac 1` makes. The service does not decode other formats. An empty body or an odd byte count
is 422; more than *Longest audio per call* (`MOONSHINE_MAX_SECONDS`, default 150, at most 900) is 413.

**Query options.** `language` (default `en`; `auto` is the same as `en`; any other code is 422), `beam_size` and
`word_timestamps` (accepted so Whisper-shaped callers work, both ignored), `stream` (default `false`). Any other option
is refused with 422.

**Phrases.** Moonshine handles clips up to about 30 s, so the audio is split at pauses of 0.5 s or more and each phrase
is one segment (`start_s`/`end_s` are its edges, with 0.2 s of quiet kept on each side). A phrase over 30 s is cut at its
quietest point. `words` is always empty. A phrase followed by a pause is finished: its text is remembered (256 per loaded
model, by a hash of its audio), so live dictation, which re-sends the whole growing window every second, only decodes
the phrase being spoken. Speech level 0.01 (about -40 dBFS) counts as speech; a room that is never quieter than that
has no pauses, and the audio is cut at 30 s instead.

**Result.** `segments` are `{"start_s", "end_s", "text"}`; `words` is always empty; `text` joins the non-empty segments with a space. An empty `text` is valid (silence).

**Streaming, per segment.** With `stream=true` the reply is `application/x-ndjson`: one
`{"type": "segment", "start_s", "end_s", "text"}` line per segment, then `{"type": "done", ...}` holding the same body a
call without `stream` returns. A refusal before the first segment is a normal HTTP error; a failure after it is sent as
`{"type": "error", "status", "message"}` and ends the stream. A kept answer is streamed back segment by segment.

**Cache.** *Answers kept per replica* (`MOONSHINE_CACHE_SIZE`, default 256, 0 = off) keeps the last answers for the same
audio and options and sends them again without transcribing (`X-Cache: hit`). Decoding is deterministic, so every request
is kept. New weights empty the cache. The cache is per replica, so with N replicas the hit rate is about 1/N.

**Tokens.** A token's "allowed projects" list has no effect here: there is one model and no project models.

## Admin page

`/admin/` (password `MOONSHINE_ADMIN_PASSWORD`): tokens with rate limit and expiry, usage numbers, CPU threads, the
Settings card (update check hours, in-flight cap, answers kept, longest audio, and the restart options
model, number format, load at start), and the Updates card (**Check now** and **Download new weights** for the Hugging
Face repository). New weights are downloaded once into the shared models volume; the other replicas notice within a few
seconds and load them on their next request. `/metrics` (admin password) is Prometheus text per token.
`moonshine_request_seconds` is a histogram of how long each `/v1` call took on the replica that answers.

Changing the CPU threads reloads the model on that replica (onnxruntime fixes its threads when the session is built); the
next call loads it again. Set the value to the physical core count.

## Run

```bash
docker compose up -d --build        # http://<host>:9240
```

Without Docker: `run.bat` (uv, listens on `127.0.0.1:9240`). The first transcription downloads the model (about 250 MB
for `base` float, less for `quantized` or `tiny`). See `deployment.md`.

Example (needs `ffmpeg`):

```bash
ffmpeg -v error -i speech.wav -f s16le -ar 16000 -ac 1 - | curl -X POST "http://127.0.0.1:9240/v1/transcribe" \
  -H "X-Internal-Token: moonshine_..." --data-binary @-
```

## Tests

```bash
uv sync
uv run pytest
```

The tests use a fake model; none loads real weights. `tools/smoke.py` runs the real model once.

## Limits worth knowing

- One transcription at a time per replica; extra calls wait, and more than the in-flight cap get 429.
- The rate limit is per replica.
- Speed, measured on a 12-thread desktop CPU with `base` float and 2 threads: 8.4 s of speech in 0.7 s (about 12x real
  time). Not yet measured on the deployment machine: run `uv run python tools/smoke.py <file.wav> <threads>` there.
- English only; no punctuation or casing control, no timestamps inside a piece.
- Model errors are never sent to the caller (they can hold paths): the reply is "Transcription failed. Try again."


## Try it from the admin page

Open `/admin/` and use **Try it** to call the public API with a service token held only in memory. Runs use normal token scopes, limits and caches; the panel shows HTTP status, latency, responses, cancellation and a curl equivalent with a token placeholder. See [the web UI guide](docs/guide-web-ui.md#try-it-send-a-real-request).

Transcribe accepts an audio file and sends raw 16 kHz mono signed 16-bit little-endian PCM to `POST /v1/transcribe`. Browser-decodable encoded audio is converted in the browser; raw `.pcm` input must already have that format. Language, beam size, word timestamps and streaming are query options. Decoded audio is capped at 150 seconds in the browser; the server can impose a lower limit. The curl body for converted audio is `@input.pcm`, not the original encoded file.
