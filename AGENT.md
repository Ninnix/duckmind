# duckmind agent notes

## Project

Unofficial Python client for https://duck.ai (DuckDuckGo AI Chat).  No API key. Minimal deps.

## Architecture

- `client.py` — DuckMind class: ask(), stream(), ask_with_image(), warm-up, retry/backoff, history toggle
- `_challenge.py` — JS challenge solver (x-vqd-hash-1) via mini-racer + DOM stubs
- `_stubs.js` — minimal browser DOM mock (~11KB) for the challenge engine
- `_durable.py` — RSA-OAEP JWK generation for durable streams
- `models.py` — model aliases, capability map, effort resolution, data types (History, Message, ImagePart, Role)
- `cli.py` — REPL (duckmind> prompt) + one-shot -p mode
- `exceptions.py` — DuckMindError, RatelimitError, ChallengeError, etc.

## Key details

- Challenge: async JS IIFE base64 in `x-vqd-hash-1` header. Runs in mini-racer with stubs. The response `meta` must include `origin`, `stack`, `duration` fields (injected after solve).
- Rate-limit: ~1 req/15s per IP. Inner retry on 429 (5s/10s backoff), outer retry with 2s base backoff.
- Warm-up: visits duck.ai homepage and SERP to seed cookies before first chat.
- Effort: some models may have `fast`, `thinking` levels. resolve_effort() maps user-facing "fast"/"reasoning" to model-specific values. Fast is default.

## Style

- Minimal, readable, no bloat
- Comments explain *why*, not *what*
- No frameworks, no async, no type-checkers at runtime
- Import new deps only if strictly necessary

## Testing

```bash
pytest tests/ -v
```

## Build

```bash
pip install -e .
```
