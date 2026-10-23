# duckmind agent notes

## Project

Unofficial Python client for https://duck.ai (DuckDuckGo AI Chat).  No API key. Minimal deps.

## Architecture

- `client.py` — DuckMind class: ask(), stream(), ask_with_image(), warm-up, retry/backoff, history toggle
- `_challenge.py` — JS challenge solver (x-vqd-hash-1) via mini-racer + DOM stubs
- `_stubs.js` — minimal browser DOM mock (~11KB) for the challenge engine
- `_durable.py` — standard-library RSA-OAEP public JWK generation for durable streams
- `_http.py` — standard-library HTTP, cookies, proxies and streaming decompression
- `models.py` — model aliases, capability map, effort resolution, data types (History, Message, ImagePart, Role)
- `cli.py` — themed interactive REPL and one-shot -p mode
- `ui.py` — shared banner, prompt, table, picker, line-editor and spinner helpers
- `exceptions.py` — DuckMindError, RatelimitError, ChallengeError, etc.

## Key details

- Challenge: async JS IIFE base64 in `x-vqd-hash-1` header. Runs in mini-racer with stubs. The response `meta` must include `origin`, `stack`, `duration` fields (injected after solve).
- Rate-limit: ~1 req/15s per IP. One bounded retry loop honors Retry-After; consecutive POSTs wait at least 15 seconds. Status URLs are unique to avoid cached challenges.
- Warm-up: visits duck.ai homepage and SERP to seed cookies before first chat.
- Effort: some models may have `fast`, `thinking` levels. resolve_effort() maps user-facing "fast"/"reasoning" to model-specific values. Fast is default; GPT Luna (`gpt-6-luna`) is the default model.
- Interactive: `/models` picks free models, `/models-all` includes subscription tiers, Tab cycles effort, and Ctrl+W toggles web search.

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
