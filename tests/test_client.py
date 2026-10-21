import sys
import pytest

sys.path.insert(0, "src")

from duckmind import (
    ChallengeError,
    DuckMind,
    DuckMindError,
    GPT4oMini,
    GPT5Mini,
    GPT6Luna,
    GPT54Mini,
    GPT56Terra,
    GPT56Sol,
    ClaudeOpus48,
    Gemma4,
    ClaudeHaiku,
    ImagePart,
    Llama4Scout,
    Message,
    MistralSmall,
    RatelimitError,
    Role,
    list_models,
    model_supports_vision,
    model_supports_web_search,
    resolve_effort,
    resolve_model,
)


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    monkeypatch.setattr(DuckMind, "_warm", lambda self: None)


def test_resolve_model():
    assert resolve_model("gpt4") == GPT4oMini
    assert resolve_model("gpt-4o-mini") == GPT4oMini
    assert resolve_model("gpt5") == GPT5Mini
    assert resolve_model("claude") == ClaudeHaiku
    assert resolve_model("llama") == Llama4Scout
    assert resolve_model("mistral") == MistralSmall
    assert resolve_model(None) == GPT6Luna
    assert resolve_model("gpt-luna") == GPT6Luna
    assert resolve_model("gtp-luna") == GPT6Luna
    assert resolve_model("unknown-model-xyz") == "unknown-model-xyz"


def test_list_models():
    models = list_models()
    assert GPT4oMini not in models
    assert GPT5Mini not in models
    assert GPT6Luna in models
    assert ClaudeHaiku in models
    assert Llama4Scout not in models
    assert MistralSmall in models
    assert len(models) == 11
    assert GPT54Mini in list_models("free")
    assert Gemma4 in list_models("free")
    assert GPT56Terra not in list_models("free")
    assert GPT56Terra in list_models("plus")
    assert GPT56Sol not in list_models("plus")
    assert ClaudeOpus48 in list_models("pro")
    with pytest.raises(ValueError):
        list_models("unknown")


def test_model_capabilities():
    assert model_supports_web_search("gpt-4o-mini") is False
    assert model_supports_web_search("gpt-5.4-mini") is True
    assert model_supports_web_search("luna") is True
    assert model_supports_web_search("claude-haiku-4-5") is True
    assert model_supports_web_search("llama") is False
    assert model_supports_vision("gpt-6-luna") is True
    assert model_supports_vision("gemma") is True
    assert model_supports_vision("llama") is False


def test_resolve_effort():
    assert resolve_effort("gpt-4o-mini", "fast") is None
    assert resolve_effort("gpt-5.4-mini", None) == "none"
    assert resolve_effort("gpt-5.4-mini", "fast") == "none"
    assert resolve_effort("luna", "fast") == "none"
    assert resolve_effort("luna", "reasoning") == "low"
    assert resolve_effort("gpt-5.4-mini", "reasoning") == "medium"
    assert resolve_effort("claude-haiku-4-5", "fast") == "none"
    assert resolve_effort("claude-haiku-4-5", "reasoning") == "low"


def test_message_to_dict():
    msg = Message(role=Role.User, content="hello")
    assert msg.to_dict() == {"role": "user", "content": "hello"}

    msg2 = Message(role=Role.Assistant, content="hi")
    assert msg2.to_dict() == {"role": "assistant", "content": "hi"}


def test_image_part():
    ip = ImagePart.from_bytes(b"fakebytes", mime_type="image/png")
    assert ip.image.startswith("data:image/png;base64,")
    part = ip.to_part()
    assert part["type"] == "image"
    assert part["mimeType"] == "image/png"


def test_exception_hierarchy():
    assert issubclass(ChallengeError, DuckMindError)
    assert issubclass(RatelimitError, DuckMindError)


def test_duckmind_init():
    d = DuckMind()
    assert d.model == GPT6Luna
    assert d.history_enabled is False
    d.close()


def test_duckmind_init_custom():
    d = DuckMind(model="claude", effort="fast", timeout=30, max_retries=2, history=True)
    assert d.model == ClaudeHaiku
    assert d.history_enabled is True
    assert d.max_retries == 2
    d.close()


def test_duckmind_history_toggle():
    d = DuckMind()
    assert d.history_enabled is False
    d.enable_history()
    assert d.history_enabled is True
    d.disable_history()
    assert d.history_enabled is False
    d.close()


def test_duckmind_reset():
    d = DuckMind(history=True)
    d.history.add_user("hello")
    assert len(d.history.messages) == 1
    d.reset()
    assert len(d.history.messages) == 0
    d.close()
