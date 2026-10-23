"""
duckmind CLI — ds4-style chat client for DuckDuckGo AI Chat (duck.ai).
"""

from __future__ import annotations

import argparse
import queue
import sys
import threading
from typing import Optional

from . import (
    DuckMind,
    ImagePart,
    list_models,
    model_supports_vision,
    model_supports_web_search,
    resolve_effort,
    resolve_model,
)
from .models import MODEL_ALIASES
from .ui import PickerItem, Theme, UI, read_text_file, truncated

MODEL_NAMES = {
    "luna": "gpt-6-luna",
    "mini": "gpt-5.4-mini",
    "claude": "claude-haiku-4-5",
    "mistral": "mistral-small-2603",
    "gpt-oss": "tinfoil/gpt-oss-120b",
    "gemma": "tinfoil/gemma4-31b",
    "terra": "gpt-5.6-terra",
    "sonnet4.6": "claude-sonnet-4-6",
    "sonnet5.5": "claude-sonnet-5-5",
    "sol": "gpt-5.6-sol",
    "opus": "claude-opus-4-8",
}

THEME = Theme("DuckMind", "🪿", 208, "Duck.ai · no API key")
ALIASES: dict[str, str] = {}
for _alias, _model in MODEL_NAMES.items():
    ALIASES.setdefault(_model, _alias)


def _usage(fp) -> None:
    from . import __version__

    fp.write(
        f"duckmind v{__version__} — duck.ai CLI\n"
        f"\n"
        f"Usage: duckmind [(-p PROMPT | ask PROMPT | PROMPT...)] [options]\n"
        f"\n"
        f"Invocation modes:\n"
        f"  duckmind\n"
        f"      Start the interactive chat prompt.\n"
        f"  duckmind -p TEXT\n"
        f"      Run one prompt and exit.\n"
        f"  duckmind ask TEXT\n"
        f"      Same as -p.\n"
        f"\n"
        f"Options:\n"
        f"  -m, --model NAME\n"
        f"      Model alias or full identifier (default: luna / gpt-6-luna).\n"
        f"  --image PATH\n"
        f"      Attach an image and prompt \"Describe this image\".\n"
        f"  --web\n"
        f"      Enable web search for a one-shot prompt.\n"
        f"  --effort fast|reasoning\n"
        f"      Reasoning effort for a one-shot prompt.\n"
        f"  --models\n"
        f"      List free models and exit.\n"
        f"  --models-all\n"
        f"      List every model, including premium tiers.\n"
        f"  --no-color\n"
        f"      Disable ANSI colour.\n"
        f"  --version\n"
        f"      Show the version and exit.\n"
        f"  -h, --help\n"
        f"      Show this help.\n"
        f"\n"
        f"Interactive commands:\n"
        f"  /help             Show this help.\n"
        f"  /models           Pick a free model interactively.\n"
        f"  /models-all       Pick from every model, including premium.\n"
        f"  /model [N|NAME]   Show or switch the current model.\n"
        f"  /status           Show the active model and settings.\n"
        f"  /effort EFF       Reasoning effort: fast or reasoning; Tab cycles it.\n"
        f"  /history [on|off] Show history, or toggle multi-turn memory.\n"
        f"  /web [on|off]     Toggle web search; Ctrl+W also toggles it.\n"
        f"  /image PATH [TXT] Send an image with an optional prompt.\n"
        f"  /read FILE        Read prompt from FILE and run it.\n"
        f"  /clear            Clear conversation history.\n"
        f"  /quit, /exit      Leave the prompt.\n"
        f"  Ctrl+C            Stop generation; Ctrl+D to exit.\n"
    )


def _model_choices(access: Optional[str] = None) -> list[dict[str, str]]:
    free = set(list_models("free"))
    plus = set(list_models("plus"))
    choices = []
    for model in list_models():
        tier = "free" if model in free else "Plus subscription" if model in plus else "Pro subscription"
        caps = []
        if model_supports_vision(model):
            caps.append("vision")
        if model_supports_web_search(model):
            caps.append("web")
        if resolve_effort(model, None) is not None:
            caps.append("reasoning")
        choices.append({
            "id": model,
            "alias": ALIASES.get(model, ""),
            "access": tier,
            "caps": ", ".join(caps),
        })
    if access == "free":
        choices = [choice for choice in choices if choice["access"] == "free"]
    elif access == "plus":
        choices = [choice for choice in choices if choice["access"] == "Plus subscription"]
    elif access == "pro":
        choices = [choice for choice in choices if choice["access"] == "Pro subscription"]
    return choices


def _print_models(ui: Optional[UI] = None, current: Optional[str] = None, access: Optional[str] = None) -> list[dict[str, str]]:
    ui = ui or UI(THEME)
    choices = _model_choices(access)
    selected = resolve_model(current) if current else "gpt-6-luna"
    rows = []
    for index, choice in enumerate(choices, 1):
        mark = ui.accent("●") if choice["id"] == selected else " "
        label = choice["id"]
        if choice["alias"]:
            label += f" ({choice['alias']})"
        rows.append([
            mark,
            ui.dim(str(index)),
            ui.bold(label) if choice["id"] == selected else label,
            choice["access"],
            ui.dim(choice["caps"]),
        ])
    footer = f"Current: {selected} · switch with /model <number|alias|id>"
    if not choices:
        ui.hint(f"No model matches {access!r}.")
    else:
        title = f"Models · {THEME.name}" + (f" · {access}" if access else "")
        ui.table(title, ["", "#", "MODEL", "ACCESS", "CAPS"], rows,
                 align_right=(1,), footer=footer)
    return choices


def _list_models() -> None:
    """Backwards-compatible helper used by the transport tests."""
    _print_models()


def _print_help(ui: UI, model: str) -> None:
    ui.commands((
        ("/help", "Show this help."),
        ("/models", "Pick a free model interactively."),
        ("/models-all", "Pick from all models, including premium."),
        ("/model [N|name]", "Show or switch the active model."),
        ("/status", "Show model, effort, web and history state."),
        ("/effort [fast|reasoning]", "Set effort; Tab cycles it at the prompt."),
        ("/history [on|off]", "Show the conversation or toggle memory."),
        ("/web [on|off]", "Toggle web search; Ctrl+W also toggles it."),
        ("/image PATH [text]", "Send a local image."),
        ("/read FILE", "Send a text file as the next prompt."),
        ("/clear", "Clear conversation history."),
        ("/quit, /exit", "Leave the prompt."),
    ))
    ui.hint(f"Current model: {model} · aliases: {', '.join(MODEL_NAMES)}")


def _print_header(ui: UI, model: str, effort: Optional[str], web: bool, history: bool) -> None:
    from . import __version__

    ui.banner(
        __version__,
        facts=(
            f"model {model}",
            f"effort {effort or 'fast'}",
            f"web {'on' if web else 'off'}",
            f"history {'on' if history else 'off'}",
        ),
        hint="/help · Tab effort · Ctrl+W web · /models switch · Ctrl+D quit",
    )


def _parse_choice(token: str, choices: list[dict[str, str]]) -> tuple[str, bool]:
    token = token.strip()
    if not token:
        raise ValueError("model name is empty")
    if token.isdigit():
        index = int(token)
        if not 1 <= index <= len(choices):
            raise ValueError(f"model number must be between 1 and {len(choices)}")
        return choices[index - 1]["id"], True
    resolved = resolve_model(token)
    known = {choice["id"] for choice in choices}
    return resolved, resolved in known


def _switch_model(ui: UI, value: str, choices: list[dict[str, str]], state: dict) -> None:
    try:
        selected, known = _parse_choice(value, choices)
    except ValueError as error:
        ui.error(str(error))
        return
    state["model"] = selected
    client = state.get("client")
    if client is not None:
        client.model = selected
        client.history.model = selected
        client._pending_hash = None
    if known:
        ui.success(f"model → {selected}")
    else:
        ui.hint(f"model → {selected} (not in the catalog; the request may fail)")


def _pick_model(ui: UI, choices: list[dict[str, str]], current: str, title: str, access: Optional[str] = None) -> Optional[str]:
    if not choices:
        ui.hint("No models available.")
        return None
    if not ui.interactive:
        _print_models(ui, current, access)
        ui.hint("Interactive picker needs a terminal; use /model <number|alias|id>.")
        return None
    items = []
    for choice in choices:
        label = choice["id"]
        if choice["alias"]:
            label += f" ({choice['alias']})"
        detail = choice["access"]
        if choice["caps"]:
            detail += f" · {choice['caps']}"
        items.append(PickerItem(value=choice["id"], label=label, detail=detail))
    return ui.pick(title, items, current=current)


def _status(ui: UI, model: str, effort: Optional[str], web: bool, history: bool) -> None:
    rows = [
        ["provider", "duck.ai"],
        ["model", model],
        ["effort", effort or "fast"],
        ["web", "on" if web else "off"],
        ["history", "on" if history else "off"],
    ]
    ui.table("Status", ["SETTING", "VALUE"], rows)


def _show_history(ui: UI, client: Optional[DuckMind], history_enabled: bool) -> None:
    messages = client.history.messages if client is not None else []
    if not messages:
        ui.hint("(history is empty)")
        return
    ui.section("History")
    for message in messages:
        content = message.content
        if isinstance(content, list):
            content = " ".join(str(part) for part in content)
        print(f"  {ui.accent(message.role + ':')} {truncated(str(content), 200)}", file=ui.out)
    print(file=ui.out)
    ui.hint(f"history {'on' if history_enabled else 'off'} · /clear clears it")


def _repl(
    ui: UI,
    model: Optional[str] = None,
    web: bool = False,
    effort: Optional[str] = None,
) -> None:
    import atexit

    state: dict = {"client": None, "model": resolve_model(model) if model else "gpt-6-luna"}
    web_search = bool(web)
    history_enabled = True

    def toggle_effort() -> str:
        nonlocal effort
        effort = "reasoning" if effort != "reasoning" else None
        return f"{ui.dim('effort')} {ui.accent(effort or 'fast')}"

    def toggle_web() -> str:
        nonlocal web_search
        web_search = not web_search
        return f"{ui.dim('web')} {ui.accent('on' if web_search else 'off')}"

    commands = (
        "/help", "/models", "/models-all", "/model", "/status", "/effort",
        "/history", "/web", "/image", "/read", "/clear", "/quit", "/exit",
    )

    def ensure_client() -> DuckMind:
        client = state.get("client")
        if client is None:
            client = DuckMind(model=state["model"], history=history_enabled)
            state["client"] = client
        return client

    def close_client() -> None:
        client = state.get("client")
        if client is not None:
            try:
                client.close()
            except Exception:
                pass
            state["client"] = None

    atexit.register(close_client)
    _print_header(ui, state["model"], effort, web_search, history_enabled)

    while True:
        try:
            line = ui.readline(
                ui.prompt(),
                completions=commands,
                on_tab=toggle_effort,
                on_ctrl_w=toggle_web,
            )
        except EOFError:
            print(file=ui.out)
            break
        except KeyboardInterrupt:
            print(file=ui.out)
            continue

        line = line.strip()
        if not line:
            continue

        if line.startswith("/"):
            command, _, arg = line.partition(" ")
            command = command.lower().strip()
            arg = arg.strip()

            if command in ("/quit", "/exit", "/q"):
                ui.hint("Bye.")
                break

            if command == "/help":
                _print_help(ui, state["model"])

            elif command in ("/models", "/models-all"):
                show_all = command == "/models-all"
                access = None if show_all else "free"
                choices = _model_choices(access)
                if arg:
                    _switch_model(ui, arg, choices, state)
                else:
                    title = f"Models · {THEME.name} · {'all' if show_all else 'free'}"
                    selected = _pick_model(ui, choices, state["model"], title, access)
                    if selected:
                        _switch_model(ui, selected, choices, state)

            elif command == "/model":
                if not arg:
                    choices = _model_choices("free")
                    selected = _pick_model(
                        ui, choices, state["model"], f"Models · {THEME.name} · free", "free"
                    )
                    if selected:
                        _switch_model(ui, selected, choices, state)
                else:
                    choices = _model_choices()
                    _switch_model(ui, arg, choices, state)

            elif command == "/status":
                _status(ui, state["model"], effort, web_search, history_enabled)

            elif command == "/effort":
                if not arg:
                    ui.info(f"effort: {effort or 'fast'}")
                    ui.hint("Press Tab to cycle · /effort fast|reasoning")
                    continue
                value = arg.lower()
                if value in ("fast", "reasoning", "thinking", "default"):
                    effort = "reasoning" if value in ("thinking", "reasoning") else None
                    ui.success(f"effort → {effort or 'fast'}")
                else:
                    ui.error("usage: /effort fast|reasoning")

            elif command == "/history":
                if arg.lower() in ("on", "off"):
                    history_enabled = arg.lower() == "on"
                    client = state.get("client")
                    if client is not None:
                        if history_enabled:
                            client.enable_history()
                        else:
                            client.disable_history()
                    ui.success(f"history {'on' if history_enabled else 'off'}")
                else:
                    _show_history(ui, state.get("client"), history_enabled)

            elif command == "/web":
                value = arg.lower()
                if value in ("on", "enable", "true", "1"):
                    web_search = True
                elif value in ("off", "disable", "false", "0"):
                    web_search = False
                else:
                    web_search = not web_search
                ui.success(f"web search {'on' if web_search else 'off'}")

            elif command == "/clear":
                client = state.get("client")
                if client is not None:
                    client.reset()
                ui.success("history cleared")

            elif command == "/read":
                if not arg:
                    ui.error("usage: /read FILE")
                    continue
                try:
                    text = read_text_file(arg)
                except (OSError, ValueError) as error:
                    ui.error(str(error))
                    continue
                _chat(ui, ensure_client(), text, web_search, effort)

            elif command == "/image":
                if not arg:
                    ui.error("usage: /image PATH [prompt]")
                    continue
                path, _, caption = arg.partition(" ")
                try:
                    part = ImagePart.from_path(path)
                except (OSError, ValueError) as error:
                    ui.error(str(error))
                    continue
                _chat(ui, ensure_client(), [caption.strip() or "Describe this image.", part], web_search, effort)

            else:
                ui.error(f"unknown command: {command} · type /help")

        else:
            _chat(ui, ensure_client(), line, web_search, effort)

    close_client()


def _chat(ui: UI, client: DuckMind, text, web_search: bool, effort: Optional[str] = None) -> None:
    try:
        if effort != "reasoning":
            for chunk in client.stream(text, web_search=web_search, effort=effort):
                print(chunk, end="", flush=True)
            print()
            return

        q: queue.SimpleQueue = queue.SimpleQueue()

        def _run():
            try:
                for chunk in client.stream(text, web_search=web_search, effort=effort):
                    q.put(("c", chunk))
                q.put(("d", None))
            except BaseException as error:
                q.put(("e", error))

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()

        dots = 0
        item = None
        while item is None:
            sys.stdout.write(f"\r\033[2K{ui.dim('thinking' + '.' * ((dots % 3) + 1))}")
            sys.stdout.flush()
            dots += 1
            try:
                item = q.get(timeout=0.4)
            except queue.Empty:
                pass
        sys.stdout.write("\r\033[2K")
        sys.stdout.flush()

        while True:
            kind, value = item
            if kind == "c":
                sys.stdout.write(value)
                sys.stdout.flush()
            elif kind == "d":
                print()
                return
            elif kind == "e":
                raise value
            item = q.get()
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as error:
        ui.error(str(error), prefix="duckmind")


def _oneshot(
    prompt: str,
    model: Optional[str] = None,
    image: Optional[str] = None,
    web: bool = False,
    effort: Optional[str] = None,
) -> None:
    kwargs = {}
    if model:
        kwargs["model"] = model
    try:
        with DuckMind(**kwargs) as client:
            if image:
                reply = client.ask_with_image(prompt, image, web_search=web, effort=effort)
            else:
                reply = client.ask(prompt, web_search=web, effort=effort)
            print(reply)
    except Exception as error:
        print(f"duckmind: {error}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="duckmind CLI", add_help=False)
    parser.add_argument("-p", "--prompt", nargs="?", const=None, default=None)
    parser.add_argument("prompt_parts", nargs="*")
    parser.add_argument("--image", default=None)
    parser.add_argument("--models", action="store_true")
    parser.add_argument("--models-all", action="store_true")
    parser.add_argument("-m", "--model", default=None)
    parser.add_argument("--web", action="store_true")
    parser.add_argument("--effort", choices=("fast", "reasoning"), default=None)
    parser.add_argument("--no-color", action="store_true")
    parser.add_argument("--version", action="store_true")
    parser.add_argument("-h", "--help", action="store_true")
    args = parser.parse_args()

    ui = UI(THEME, enabled=False if args.no_color else None)

    if args.version:
        from . import __version__
        print(f"duckmind {__version__}")
        return

    if args.help:
        _usage(sys.stdout)
        return

    if args.models or args.models_all:
        _print_models(ui, args.model, None if args.models_all else "free")
        return

    prompt = args.prompt
    if prompt is None:
        parts = list(args.prompt_parts)
        if parts and parts[0].lower() == "ask":
            parts = parts[1:]
        prompt = " ".join(parts) if parts else None

    if prompt is not None or args.image:
        _oneshot(
            prompt if prompt is not None else "Describe this image.",
            model=args.model,
            image=args.image,
            web=args.web,
            effort=args.effort,
        )
        return

    _repl(ui, model=args.model, web=args.web, effort=args.effort)


if __name__ == "__main__":
    main()
