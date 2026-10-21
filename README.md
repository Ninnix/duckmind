# duckmind

Unofficial Python client for DuckDuckGo AI Chat (duck.ai). No API key needed for free models.

```sh
pip install git+https://github.com/Ninnix/duckmind.git
```

## CLI

```sh
duckmind                     # interactive REPL, GPT Luna by default
duckmind -p "hello"          # one-shot
duckmind --model gemma -p "hello"
duckmind --models            # current identifiers and subscription tiers
```

Commands: `/model`, `/effort fast|reasoning`, `/history`, `/web`, `/image`, `/read`, `/clear`, `/quit`.

## API

```python
from duckmind import DuckMind, ImagePart, list_models

with DuckMind() as client:                 # gpt-6-luna, fast effort
    for chunk in client.stream("tell me a joke"):
        print(chunk, end="", flush=True)
    client.ask("capital of Italy", web_search=True)
    client.ask([ImagePart.from_path("photo.jpg"), "describe this image"])

with DuckMind(history=True) as client:
    client.ask("my name is Nico")
    client.ask("what is my name?")

print(list_models())                       # current public catalog
print(list_models("free"))                # no subscription required
```

`luna`, `gpt-luna`, `gpt-6-luna` and `gtp-luna` select GPT Luna. Both the API and CLI use it by default. `effort="fast"` uses the model's lowest supported reasoning setting; `effort="reasoning"` uses its highest supported setting. GPT Luna supports `none` and `low`.

## Models

Catalog checked against [Duck.ai's frontend](https://duck.ai/) on 2026-10-21. Free models are also available on Plus and Pro; Plus models are also available on Pro. Paid models require a Duck.ai subscription session.

| Identifier | Alias | Access |
| --- | --- | --- |
| `gpt-6-luna` | `luna` | Free, default |
| `gpt-5.4-mini` | `mini` | Free |
| `claude-haiku-4-5` | `claude` | Free |
| `mistral-small-2603` | `mistral` | Free |
| `tinfoil/gpt-oss-120b` | `gpt-oss` | Free |
| `tinfoil/gemma4-31b` | `gemma` | Free |
| `gpt-5.6-terra` | `terra` | Plus |
| `claude-sonnet-4-6` | `sonnet4.6` | Plus |
| `claude-sonnet-5-5` | `sonnet5.5` / `sonnet` | Plus |
| `gpt-5.6-sol` | `sol` | Pro |
| `claude-opus-4-8` | `opus` | Pro |

GPT-4o mini, GPT-5 mini and Llama Scout have been retired from Duck.ai and are excluded from `list_models()`. Their Python constants remain importable. Explicit requests for a retired model return an actionable API error; they are not silently switched to another model. Unknown identifiers can still be passed directly.

## Transport and tests

The client discovers the current frontend version from Duck.ai's homepage during session warm-up. An explicit `fe_version=` override takes precedence. Its challenge environment uses the `duck.ai` origin. HTTP, cookies, proxies, gzip/deflate streaming and public JWK generation use Python’s standard library. The two runtime dependencies are `mini-racer` for the service’s JavaScript challenges and `html5lib` for browser-compatible HTML normalization. `httpx` and `cryptography` are removed.

A rejected challenge is discarded before retrying. Fresh status URLs prevent cached challenge reuse, consecutive chat requests share the session and wait at least 15 seconds, and HTTP 429 responses honor `Retry-After`. Retries stop after the configured number of attempts; cooldowns above 60 seconds are returned to the caller. Once visible text has streamed, a failure is raised without replaying it. A stream missing its completion marker is rejected.

```sh
pip install -e .
pip install pytest
pytest tests/ -v
```

Tests run offline and cover model aliases and tiers, defaults, frontend version discovery, streaming, challenge origin and retired-model errors. A live one-shot check is `duckmind -p "Reply with only OK"`; it uses the public service and its rate limits.

## Thanks

- [duckai](https://github.com/deedy5/duckai) — original inspiration
- [p2d-duck](https://github.com/pooraddyy/p2d-duck/) — implementation reference
