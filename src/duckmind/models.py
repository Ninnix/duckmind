from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

# Models known to work. Any string can be passed directly; these are
# just the ones we know about at release time.
GPT4oMini = "gpt-4o-mini"
GPT5Mini = "gpt-5-mini"
ClaudeHaiku = "claude-haiku-4-5"
Llama4Scout = "meta-llama/Llama-4-Scout-17B-16E-Instruct"
MistralSmall = "mistral-small-2603"
GptOss120b = "tinfoil/gpt-oss-120b"
ImageGeneration = "image-generation"

# Convenience aliases.
gpt4o_mini = GPT4oMini
gpt5_mini = GPT5Mini
claude_haiku = ClaudeHaiku
llama4_scout = Llama4Scout
mistral_small = MistralSmall
gpt_oss_120b = GptOss120b
image_gen = ImageGeneration

MODEL_ALIASES: Dict[str, str] = {
    "gpt4": GPT4oMini,
    "gpt-4": GPT4oMini,
    "gpt4o": GPT4oMini,
    "gpt-4o": GPT4oMini,
    "gpt-4o-mini": GPT4oMini,
    "gpt4o_mini": GPT4oMini,
    "gpt5": GPT5Mini,
    "gpt-5": GPT5Mini,
    "gpt-5-mini": GPT5Mini,
    "gpt5_mini": GPT5Mini,
    "claude": ClaudeHaiku,
    "claude-haiku": ClaudeHaiku,
    "claude_haiku": ClaudeHaiku,
    "claude-haiku-4-5": ClaudeHaiku,
    "haiku": ClaudeHaiku,
    "llama": Llama4Scout,
    "llama4": Llama4Scout,
    "llama-4": Llama4Scout,
    "llama4-scout": Llama4Scout,
    "llama4_scout": Llama4Scout,
    "mistral": MistralSmall,
    "mistral-small": MistralSmall,
    "mistral_small": MistralSmall,
    "mistral-small-2603": MistralSmall,
    "gpt-oss": GptOss120b,
    "gpt_oss": GptOss120b,
    "gpt-oss-120b": GptOss120b,
    "gpt_oss_120b": GptOss120b,
    "image-generation": ImageGeneration,
    "image_generation": ImageGeneration,
    "image": ImageGeneration,
    "img": ImageGeneration,
}

_MODEL_CAPS: Dict[str, Dict[str, object]] = {
    GPT4oMini: {"reasoning": False, "vision": True, "web_search": True},
    GPT5Mini: {
        "reasoning": True, "vision": True, "web_search": True,
        "fast": "minimal", "default": "minimal", "thinking": "low",
    },
    ClaudeHaiku: {
        "reasoning": True, "vision": True, "web_search": True,
        "fast": "none", "default": "low", "thinking": "low",
    },
    Llama4Scout: {"reasoning": False, "vision": False, "web_search": False},
    MistralSmall: {"reasoning": False, "vision": False, "web_search": False},
    GptOss120b: {
        "reasoning": True, "vision": False, "web_search": False,
        "fast": "low", "default": "low", "thinking": "low",
    },
    ImageGeneration: {"reasoning": False, "vision": True, "web_search": False},
}


def resolve_model(name: Optional[str]) -> str:
    if not name:
        return GPT4oMini
    return MODEL_ALIASES.get(name.strip().lower(), name.strip())


def resolve_effort(model: str, effort: Optional[str]) -> Optional[str]:
    caps = _MODEL_CAPS.get(resolve_model(model), {})
    if not caps.get("reasoning"):
        return None
    if effort is None:
        return caps.get("default")
    e = effort.strip().lower()
    if e == "fast":
        return caps.get("fast")
    if e in ("reasoning", "thinking", "slow", "high"):
        return caps.get("thinking")
    return effort


def model_supports_web_search(model: str) -> bool:
    return bool(_MODEL_CAPS.get(resolve_model(model), {}).get("web_search"))


def model_supports_vision(model: str) -> bool:
    return bool(_MODEL_CAPS.get(resolve_model(model), {}).get("vision"))


def list_models() -> List[str]:
    return list(_MODEL_CAPS.keys())


class Role:
    User = "user"
    Assistant = "assistant"
    System = "system"


@dataclass
class ImagePart:
    image: str
    mime_type: str = "image/png"

    @classmethod
    def from_bytes(cls, data: bytes, mime_type: str = "image/png") -> "ImagePart":
        b64 = base64.b64encode(data).decode("ascii")
        return cls(image=f"data:{mime_type};base64,{b64}", mime_type=mime_type)

    @classmethod
    def from_path(cls, path: str, mime_type: Optional[str] = None) -> "ImagePart":
        mt = mime_type or mimetypes.guess_type(path)[0] or "image/png"
        with open(path, "rb") as f:
            return cls.from_bytes(f.read(), mime_type=mt)

    def to_part(self) -> dict:
        return {"type": "image", "mimeType": self.mime_type, "image": self.image}


Content = Union[str, List[Union[str, ImagePart, dict]]]


@dataclass
class Message:
    role: str
    content: Content

    def to_dict(self) -> dict:
        if isinstance(self.content, str):
            return {"role": self.role, "content": self.content}
        parts: List[dict] = []
        for p in self.content:
            if isinstance(p, str):
                parts.append({"type": "text", "text": p})
            elif isinstance(p, ImagePart):
                parts.append(p.to_part())
            elif isinstance(p, dict):
                parts.append(p)
            else:
                raise TypeError(f"unsupported content part: {type(p).__name__}")
        return {"role": self.role, "content": parts}


@dataclass
class History:
    model: str = GPT4oMini
    messages: List[Message] = field(default_factory=list)

    def add_user(self, content: Content) -> None:
        self.messages.append(Message(role=Role.User, content=content))

    def add_assistant(self, content: str) -> None:
        self.messages.append(Message(role=Role.Assistant, content=content))

    def to_messages(self) -> List[dict]:
        return [m.to_dict() for m in self.messages]

    def clear(self) -> None:
        self.messages.clear()
