from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

# Duck.ai catalog checked 2026-10-21. Unknown identifiers may still be passed through.
GPT6Luna = "gpt-6-luna"
GPT54Mini = "gpt-5.4-mini"
ClaudeHaiku = "claude-haiku-4-5"
MistralSmall = "mistral-small-2603"
GptOss120b = "tinfoil/gpt-oss-120b"
Gemma4 = "tinfoil/gemma4-31b"
GPT56Terra = "gpt-5.6-terra"
ClaudeSonnet46 = "claude-sonnet-4-6"
ClaudeSonnet55 = "claude-sonnet-5-5"
GPT56Sol = "gpt-5.6-sol"
ClaudeOpus48 = "claude-opus-4-8"

# Keep historical identifiers importable without presenting retired models as available.
GPT4oMini = "gpt-4o-mini"
GPT5Mini = "gpt-5-mini"
Llama4Scout = "meta-llama/Llama-4-Scout-17B-16E-Instruct"
ImageGeneration = "image-generation"

gpt4o_mini = GPT4oMini
gpt5_mini = GPT5Mini
llama4_scout = Llama4Scout
image_gen = ImageGeneration
gpt6_luna = GPT6Luna
gpt54_mini = GPT54Mini
claude_haiku = ClaudeHaiku
mistral_small = MistralSmall
gpt_oss_120b = GptOss120b
gemma4 = Gemma4
gpt56_terra = GPT56Terra
claude_sonnet46 = ClaudeSonnet46
claude_sonnet55 = ClaudeSonnet55
gpt56_sol = GPT56Sol
claude_opus48 = ClaudeOpus48

MODEL_ALIASES: Dict[str, str] = {
    "luna": GPT6Luna,
    "gpt-luna": GPT6Luna,
    "gtp-luna": GPT6Luna,
    "gpt6": GPT6Luna,
    "gpt-6": GPT6Luna,
    "gpt6_luna": GPT6Luna,
    "gpt54-mini": GPT54Mini,
    "gpt5.4-mini": GPT54Mini,
    "mini": GPT54Mini,
    "terra": GPT56Terra,
    "gpt56-terra": GPT56Terra,
    "sol": GPT56Sol,
    "gpt56-sol": GPT56Sol,
    "claude": ClaudeHaiku,
    "haiku": ClaudeHaiku,
    "claude-haiku": ClaudeHaiku,
    "claude_haiku": ClaudeHaiku,
    "sonnet": ClaudeSonnet55,
    "sonnet4.6": ClaudeSonnet46,
    "sonnet5.5": ClaudeSonnet55,
    "opus": ClaudeOpus48,
    "opus4.8": ClaudeOpus48,
    "gemma": Gemma4,
    "gemma4": Gemma4,
    "mistral": MistralSmall,
    "mistral-small": MistralSmall,
    "mistral_small": MistralSmall,
    "gpt-oss": GptOss120b,
    "gpt_oss": GptOss120b,
    "gpt-oss-120b": GptOss120b,
    "gpt_oss_120b": GptOss120b,
    "gpt4": GPT4oMini,
    "gpt-4": GPT4oMini,
    "gpt4o": GPT4oMini,
    "gpt-4o": GPT4oMini,
    "gpt4o_mini": GPT4oMini,
    "gpt5": GPT5Mini,
    "gpt-5": GPT5Mini,
    "gpt5_mini": GPT5Mini,
    "llama": Llama4Scout,
    "llama4": Llama4Scout,
    "llama-4": Llama4Scout,
    "llama4-scout": Llama4Scout,
    "llama4_scout": Llama4Scout,
    "image": ImageGeneration,
    "img": ImageGeneration,
    "image_generation": ImageGeneration,
}

_MODEL_CAPS: Dict[str, Dict[str, object]] = {
    GPT6Luna: {
        "vision": True, "web_search": True,
        "tiers": ('internal', 'free', 'plus', 'pro'),
        "reasoning": True, "fast": 'none', "default": 'none', "thinking": 'low',
    },
    GPT54Mini: {
        "vision": True, "web_search": True,
        "tiers": ('free', 'plus', 'pro', 'internal'),
        "reasoning": True, "fast": 'none', "default": 'none', "thinking": 'medium',
    },
    ClaudeHaiku: {
        "vision": True, "web_search": True,
        "tiers": ('free', 'plus', 'pro', 'internal'),
        "reasoning": True, "fast": 'none', "default": 'none', "thinking": 'low',
    },
    MistralSmall: {
        "vision": False, "web_search": False,
        "tiers": ('free', 'plus', 'pro', 'internal'),
    },
    GptOss120b: {
        "vision": False, "web_search": True,
        "tiers": ('free', 'plus', 'pro', 'internal'),
        "reasoning": True, "fast": 'low', "default": 'low', "thinking": 'low',
    },
    Gemma4: {
        "vision": True, "web_search": True,
        "tiers": ('internal', 'free', 'plus', 'pro'),
        "reasoning": True, "fast": 'none', "default": 'none', "thinking": 'low',
    },
    GPT56Terra: {
        "vision": True, "web_search": True,
        "tiers": ('plus', 'pro', 'internal'),
        "reasoning": True, "fast": 'none', "default": 'none', "thinking": 'medium',
    },
    ClaudeSonnet46: {
        "vision": True, "web_search": True,
        "tiers": ('plus', 'pro', 'internal'),
        "reasoning": True, "fast": 'none', "default": 'none', "thinking": 'low',
    },
    ClaudeSonnet55: {
        "vision": True, "web_search": True,
        "tiers": ('plus', 'pro', 'internal'),
        "reasoning": True, "fast": 'none', "default": 'none', "thinking": 'low',
    },
    GPT56Sol: {
        "vision": True, "web_search": True,
        "tiers": ('pro', 'internal'),
        "reasoning": True, "fast": 'none', "default": 'none', "thinking": 'medium',
    },
    ClaudeOpus48: {
        "vision": True, "web_search": True,
        "tiers": ('pro', 'internal'),
        "reasoning": True, "fast": 'none', "default": 'none', "thinking": 'medium',
    },
}


MODEL_ALIASES.update({model.lower(): model for model in _MODEL_CAPS})


def resolve_model(name: Optional[str]) -> str:
    if not name:
        return GPT6Luna
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


def list_models(access_tier: Optional[str] = None) -> List[str]:
    if access_tier is None:
        return list(_MODEL_CAPS)
    tier = access_tier.lower()
    if tier not in ("free", "plus", "pro", "internal"):
        raise ValueError("access_tier must be free, plus, pro or internal")
    return [name for name, caps in _MODEL_CAPS.items() if tier in caps["tiers"]]


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

    @classmethod
    def from_url(cls, url: str, timeout: float = 30) -> "ImagePart":
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Image URL must use HTTPS")
        request = Request(url, headers={"User-Agent": "DuckMind/1.0"})
        with urlopen(request, timeout=timeout) as response:
            if urlsplit(response.geturl()).scheme != "https":
                raise ValueError("Image URL redirect must use HTTPS")
            mime_type = response.headers.get_content_type()
            if not mime_type.startswith("image/"):
                raise ValueError("URL did not return an image")
            data = response.read(20 * 1024 * 1024 + 1)
        if len(data) > 20 * 1024 * 1024:
            raise ValueError("Image exceeds 20 MB")
        return cls.from_bytes(data, mime_type=mime_type)

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
