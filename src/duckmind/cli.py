"""
duckmind CLI — ds4-style chat client for DuckDuckGo AI Chat (duck.ai).
"""

from __future__ import annotations

import signal
import sys
import textwrap
from typing import Optional

from . import DuckMind, ImagePart, list_models
from .models import resolve_model

MODEL_NAMES = {
    "gpt4o-mini": "gpt-4o-mini",
    "gpt5-mini": "gpt-5-mini",
    "claude": "claude-haiku-4-5",
    "llama": "meta-llama/Llama-4-Scout-17B-16E-Instruct",
    "mistral": "mistral-small-2603",
    "gpt-oss": "tinfoil/gpt-oss-120b",
}


def _usage(fp) -> None:
    from . import __version__
    fp.write(
        f"duckmind v{__version__} — duck.ai CLI\n"
        f"\n"
        f"Usage: duckmind [(-p PROMPT | ask PROMPT)] [options]\n"
        f"\n"
        f"Invocation modes:\n"
        f"  duckmind\n"
        f"      Start the interactive chat prompt: duckmind>\n"
        f"  duckmind -p TEXT\n"
        f"      Run one prompt and exit.\n"
        f"  duckmind ask TEXT\n"
        f"      Same as -p.\n"
        f"\n"
        f"Options:\n"
        f"  --model NAME\n"
        f"      Model to use: gpt4o-mini (default), gpt5-mini, claude, llama, mistral, gpt-oss.\n"
        f"  --image PATH\n"
        f"      Attach an image and prompt \"Describe this image\".\n"
        f"  --models\n"
        f"      List available models and exit.\n"
        f"  -h, --help\n"
        f"      Show this help.\n"
        f"\n"
        f"Interactive commands:\n"
        f"  /help             Show this help.\n"
        f"  /model NAME       Switch model.\n"
        f"  /models           List available models.\n"
        f"  /effort EFF       Reasoning effort: fast or reasoning.\n"
        f"  /history          Toggle multi-turn memory on/off.\n"
        f"  /web              Toggle web search on/off.\n"
        f"  /image PATH       Send image as next user message.\n"
        f"  /read FILE        Read prompt from FILE and run it.\n"
        f"  /clear            Clear conversation history.\n"
        f"  /quit, /exit      Leave the prompt.\n"
        f"  Ctrl+C            Stop generation; Ctrl+D to exit.\n"
    )


def _print_help() -> None:
    _usage(sys.stdout)


def _list_models() -> None:
    print("Available models:")
    for alias, full in MODEL_NAMES.items():
        print(f"  {alias:20s} {full}")


def _print_header() -> None:
    from . import __version__
    print(f"duckmind v{__version__} — duck.ai CLI  (Ctrl+D quit, /help)")
    print()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="duckmind CLI", add_help=False)
    parser.add_argument("-p", "--prompt", nargs="?", const=None, default=None)
    parser.add_argument("prompt_text", nargs="?", default=None)
    parser.add_argument("--image", default=None)
    parser.add_argument("--models", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("-h", "--help", action="store_true")
    args, _ = parser.parse_known_args()

    if args.help:
        _usage(sys.stdout)
        return

    if args.models:
        _list_models()
        return

    prompt = args.prompt if args.prompt is not None else args.prompt_text
    if prompt is not None:
        _oneshot(prompt, model=args.model, image=args.image)
        return

    if args.image:
        _oneshot("Describe this image in one sentence.", image=args.image)
        return

    _repl()


def _oneshot(prompt: str, model: Optional[str] = None, image: Optional[str] = None) -> None:
    kwargs = {}
    if model:
        kwargs["model"] = model
    try:
        with DuckMind(**kwargs) as d:
            if image:
                r = d.ask_with_image(prompt, image)
            else:
                r = d.ask(prompt)
            print(r)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _repl() -> None:
    import atexit

    try:
        import readline  # noqa: F401 — line editing
    except ImportError:
        pass

    client: Optional[DuckMind] = None
    model = "gpt-5-mini"
    effort: Optional[str] = None
    history_enabled = True
    web_search = False

    def ensure_client() -> DuckMind:
        nonlocal client
        if client is None:
            client = DuckMind(model=model, history=history_enabled)
        return client

    def close_client() -> None:
        nonlocal client
        if client:
            try:
                client.close()
            except Exception:
                pass
            client = None

    atexit.register(close_client)

    old_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)

    _print_header()

    while True:
        try:
            line = input("duckmind> ")
        except EOFError:
            print()
            break
        except KeyboardInterrupt:
            print()
            continue

        line = line.strip()
        if not line:
            continue

        if line.startswith("/"):
            cmd, _, arg = line.partition(" ")
            cmd = cmd.lower().strip()
            arg = arg.strip()

            if cmd in ("/quit", "/exit"):
                print("Bye.")
                break

            elif cmd == "/help":
                _print_help()

            elif cmd == "/models":
                _list_models()

            elif cmd == "/model":
                if not arg:
                    print(f"Model: {model}")
                    continue
                resolved = resolve_model(arg)
                if resolved == "gpt-4o-mini" and arg.lower() not in ("gpt-4o-mini", "gpt4o-mini", "gpt4o", "gpt-4o", "gpt4"):
                    print(f"Unknown model '{arg}', using {resolved}")
                print(f"Switching to {resolved}...")
                close_client()
                model = resolved

            elif cmd == "/history":
                history_enabled = not history_enabled
                print(f"History: {'on' if history_enabled else 'off'}")
                if client is not None:
                    if history_enabled:
                        client.enable_history()
                    else:
                        client.disable_history()
                else:
                    close_client()

            elif cmd == "/web":
                web_search = not web_search
                print(f"Web search: {'on' if web_search else 'off'}")

            elif cmd == "/effort":
                if not arg:
                    print(f"Effort: {effort or 'fast'}")
                    print("Usage: /effort fast|reasoning")
                    continue
                e = arg.lower()
                if e in ("fast", "reasoning", "thinking", "default"):
                    effort = e if e != "thinking" else "reasoning"
                    print(f"Effort: {effort}")
                else:
                    print("Usage: /effort fast|reasoning")

            elif cmd == "/clear":
                if client:
                    client.reset()
                print("History cleared.")

            elif cmd == "/read":
                if not arg:
                    print("Usage: /read FILE")
                    continue
                try:
                    text = open(arg).read()
                except FileNotFoundError:
                    print(f"File not found: {arg}")
                    continue
                _chat(ensure_client(), text, web_search, effort)

            elif cmd == "/image":
                if not arg:
                    print("Usage: /image PATH")
                    continue
                try:
                    line2 = input("image> ")
                except (EOFError, KeyboardInterrupt):
                    print()
                    continue
                if line2.strip():
                    _chat(ensure_client(), [line2.strip(), ImagePart.from_path(arg)], web_search, effort)

            else:
                print(f"Unknown: {cmd}. Type /help.")

        else:
            _chat(ensure_client(), line, web_search, effort)

    close_client()
    signal.signal(signal.SIGINT, old_handler)


def _chat(client: DuckMind, text, web_search: bool, effort: Optional[str] = None) -> None:
    try:
        for chunk in client.stream(text, web_search=web_search, effort=effort):
            print(chunk, end="", flush=True)
        print()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
