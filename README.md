# duckmind

<p align="center">
  <img src="logo.png" alt="DuckMind logo" width="220">
</p>

Talk to DuckDuckGo AI Chat at duck.ai from Python or the shell. No API key is needed for free models.

```sh
pip install git+https://github.com/Ninnix/duckmind.git
```

## CLI

The prompt has an orange `🪿` banner, coloured input, streamed answers, and a model picker. Set `NO_COLOR=1` or pass `--no-color` to disable colour.

```sh
duckmind                     # interactive REPL, GPT Luna by default
duckmind -p "hello"          # one-shot
duckmind ask "hello"         # same as -p
duckmind -m gemma -p "hello" # model alias or full identifier
duckmind --models            # free models
duckmind --models-all        # every model, including premium tiers
duckmind --image photo.jpg   # one-shot image prompt
```

Commands:

- `/models` opens the free-model picker; `/models-all` includes premium models.
- `/model [N|alias|id]` opens the free picker, or switches directly.
- `/status` shows model, effort, web and history state.
- `/effort fast|reasoning` sets effort; **Tab** cycles it at the prompt.
- `/web [on|off]` toggles web search; **Ctrl+W** does the same.
- `/history [on|off]`, `/image PATH [text]`, `/read FILE`, `/clear`, `/help`, `/quit`.

Choose a model with `/models`, arrow keys, and Enter. `/models N` selects by number without opening the picker. The same picker is used by `bleo` and `gng`.

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

`ask_with_image(prompt, image)` accepts a path, bytes, data URL, or HTTPS URL. Remote images are downloaded with the standard library, limited to 20 MB, then sent as image data.

`luna`, `gpt-luna`, `gpt-6-luna` and `gtp-luna` select GPT Luna. Both the API and CLI use it by default. `effort="fast"` uses the model's lowest supported reasoning setting; `effort="reasoning"` uses its highest supported setting. GPT Luna supports `none` and `low`.

## Models

The catalog was checked against [Duck.ai](https://duck.ai/) on 2026-10-21. Free models are also available on Plus and Pro. Plus models are also available on Pro. Paid models need a Duck.ai subscription session.

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

Duck.ai has retired GPT-4o mini, GPT-5 mini, and Llama Scout. `list_models()` excludes them, but their Python constants remain importable. Requests for retired models return an API error; they are never silently switched. You can still pass an unknown identifier directly.

## Transport and tests

At session start, the client reads the frontend version from Duck.ai's homepage. Set `fe_version=` to override it. Challenges use the `duck.ai` origin. The standard library handles HTTP, cookies, proxies, compressed streams, and public JWK generation. Runtime dependencies are `mini-racer` for JavaScript challenges and `html5lib` for HTML normalization.

Rejected challenges are discarded before retrying. Fresh status URLs prevent cached challenge reuse. Consecutive chat requests share a session and wait at least 15 seconds. HTTP 429 responses honor `Retry-After`; waits above 60 seconds return to the caller. Retries stop at the configured attempt count. If a stream fails after text appears, the error is raised without replaying the text. A stream without its completion marker is rejected.

```sh
pip install -e .
pip install pytest
pytest tests/ -v
```

Tests run offline. They cover aliases, model tiers, defaults, frontend version discovery, streaming, challenge origin, and retired-model errors. For a live check, run `duckmind -p "Reply with only OK"`; this uses Duck.ai and its rate limits.

## Thanks

- [duckai](https://github.com/deedy5/duckai) — original inspiration
- [p2d-duck](https://github.com/pooraddyy/p2d-duck/) — implementation reference
