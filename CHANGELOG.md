# Changelog

## Unreleased

- Admin **Try it** panel: descriptor-driven public API requests, live text streams, JSON/media output, status and latency, cancellation and redacted curl. Auth choice (b): pasted public token stays in memory; normal scope, limits and caches apply. Shared `web/playground.js` is copied across all model and tool services.
- First version: Moonshine (`base`, float, ONNX) served on the CPU, with the admin page, tokens (rate limit,
  expiry), metrics, Settings card, update checks, weight downloads and answer cache shared with the other model
  services. Built from S1MiniModel.
- Audio is split into phrases at pauses of 0.5 s or more; each phrase is one segment, and finished phrases are remembered so live dictation (Scribe re-sends the growing window every second) only decodes the phrase being spoken. A phrase over 30 s is cut at its quietest point. No word timestamps.
- `POST /v1/transcribe` takes 16 kHz mono s16le PCM as the body and `language`, `beam_size`, `word_timestamps` and
  `stream` as query options. `stream=true` sends one JSON line per segment, then `done`.
- Settings: `max_seconds`, `vad_filter`, `compute_type` (and the shared ones).
