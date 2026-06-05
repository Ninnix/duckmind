"""
duckmind — Unofficial Python client for DuckDuckGo AI Chat (duck.ai).

Minimal, readable, no-API-key required.
"""

from .client import DuckMind
from .exceptions import APIError, ChallengeError, ConversationLimitError, DuckMindError, RatelimitError
from .models import (
    GPT4oMini,
    GPT5Mini,
    ClaudeHaiku,
    Llama4Scout,
    MistralSmall,
    GptOss120b,
    ImageGeneration,
    History,
    ImagePart,
    Message,
    Role,
    gpt4o_mini,
    gpt5_mini,
    claude_haiku,
    llama4_scout,
    mistral_small,
    gpt_oss_120b,
    image_gen,
    list_models,
    model_supports_vision,
    model_supports_web_search,
    resolve_model,
    resolve_effort,
)

__version__ = "0.1.0"

__all__ = [
    "DuckMind",
    "DuckMindError",
    "ChallengeError",
    "RatelimitError",
    "ConversationLimitError",
    "APIError",
    "GPT4oMini",
    "GPT5Mini",
    "ClaudeHaiku",
    "Llama4Scout",
    "MistralSmall",
    "GptOss120b",
    "ImageGeneration",
    "gpt4o_mini",
    "gpt5_mini",
    "claude_haiku",
    "llama4_scout",
    "mistral_small",
    "gpt_oss_120b",
    "image_gen",
    "History",
    "ImagePart",
    "Message",
    "Role",
    "list_models",
    "model_supports_vision",
    "model_supports_web_search",
    "resolve_model",
    "resolve_effort",
]

# Silence default logging.
import logging
logging.getLogger("duckmind").addHandler(logging.NullHandler())
