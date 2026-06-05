# duckmind

Unofficial Python client for DuckDuckGo AI Chat (duck.ai). No API key needed.

```bash
pip install git+https://github.com/ninnix/duckmind.git
```

## CLI

```
duckmind              # interactive REPL
duckmind -p "hello"   # one-shot
```

Commands: `/model`, `/effort fast|reasoning`, `/history`, `/web`, `/image`, `/read`, `/clear`, `/quit`.

## API

```python
from duckmind import DuckMind

client = DuckMind(model="gpt-5-mini", effort="fast")
for chunk in client.stream("tell me a joke"):
    print(chunk, end="", flush=True)
```

```python
client.ask("capital of Italy")                          # plain
client.ask([ImagePart.from_path("photo.jpg"), "desc"])  # with image
```

```python
client = DuckMind(history=True)
client.ask("my name is Nico")
client.ask("what is my name?")   # → "Nico"
```

Supported models: gpt-4o-mini, gpt-5-mini (default), claude-haiku-4-5, llama-4-scout, mistral-small-2603, gpt-oss-120b, image-generation.

## Thanks

- [duckai](https://github.com/deedy5/duckai) — original inspiration
- [p2d-duck](https://github.com/pooraddyy/p2d-duck/) — Most recent version that helped with the implementation.

