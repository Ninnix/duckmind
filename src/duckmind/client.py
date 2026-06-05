"""
Main client for DuckDuckGo AI Chat (duck.ai).

Usage:

    from duckmind import DuckMind

    with DuckMind() as client:
        print(client.ask("Hello, who are you?"))

    for chunk in DuckMind().stream("Tell me a story"):
        print(chunk, end="", flush=True)

Multi-turn (history enabled):

    with DuckMind(history=True) as client:
        client.ask("My name is Alice.")
        print(client.ask("What is my name?"))  # -> "Alice"
"""

from __future__ import annotations

import json
import logging
import random
import threading
import time
import uuid
from typing import Any, Dict, Iterator, List, Optional, Union

import httpx

from ._challenge import make_fe_signals, solve_challenge
from ._durable import generate_jwk
from .exceptions import APIError, ChallengeError, ConversationLimitError, DuckMindError, RatelimitError
from .models import (
    GPT4oMini,
    History,
    ImagePart,
    Message,
    Role,
    image_gen,
    model_supports_web_search,
    resolve_effort,
    resolve_model,
)

log = logging.getLogger("duckmind")

_BASE = "https://duck.ai"
_DDG_BASE = "https://duckduckgo.com"
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.6 Safari/605.1.15"
)
_FE_VERSION = "serp_20260424_180649_ET-0bdc33b2a02ebf8f235def65d887787f694720a1"

_TOOL_CHOICE_OFF = {
    "NewsSearch": False,
    "VideosSearch": False,
    "LocalSearch": False,
    "WeatherForecast": False,
}

_CHAT_PATH = "/duckchat/v1/chat"
_IMAGES_PATH = "/duckchat/v1/images"


class DuckMind:
    """Client for DuckDuckGo AI Chat API.

    Args:
        model: Model alias or full model id (default: gpt-4o-mini).
        effort: Reasoning effort — None (model default), "fast", or "reasoning".
        fe_version: x-fe-version header override. The library ships with a
            known-good default; override only if duck.ai's version rotates.
        timeout: HTTP timeout in seconds (default: 60).
        max_retries: Number of retries on transient errors (default: 3).
        backoff_base: Base seconds for exponential backoff (default: 2.0).
            duck.ai rate-limits to ~1 req/15s, so backoff must be generous.
        history: Enable multi-turn memory (default: False). When False every
            call is a fresh single-turn request.
        proxy: Optional proxy URL (http/socks5).
    """

    def __init__(
        self,
        model: str = GPT4oMini,
        *,
        effort: Optional[str] = None,
        fe_version: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        backoff_base: float = 2.0,
        history: bool = False,
        proxy: Optional[str] = None,
    ):
        self.model = resolve_model(model)
        self.effort = effort
        self.fe_version = fe_version or _FE_VERSION
        self.timeout = timeout
        self.max_retries = max(1, int(max_retries))
        self.backoff_base = max(0.0, float(backoff_base))
        self.proxy = proxy
        self.history_enabled = bool(history)
        self.history = History(model=self.model)
        self._jwk: Optional[Dict[str, Any]] = None
        self._jwk_lock = threading.Lock()
        self._pending_hash: Optional[str] = None

        self._client = httpx.Client(
            http2=False,
            timeout=httpx.Timeout(timeout, connect=15.0, read=timeout),
            headers=self._default_headers(),
            follow_redirects=True,
        )

        # Warm the session: visit the homepage and seed cookies.
        try:
            self._warm()
        except Exception:
            pass

    def _default_headers(self) -> Dict[str, str]:
        return {
            "User-Agent": _UA,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": f"{_BASE}/",
            "Origin": _BASE,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Ch-Ua": '"Not.A/Brand";v="99", "Chromium";v="136"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
        }

    # ------------------------------------------------------------------ ctx

    def __enter__(self) -> "DuckMind":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            pass

    def reset(self) -> None:
        self.history.clear()

    def enable_history(self) -> None:
        self.history_enabled = True

    def disable_history(self) -> None:
        self.history_enabled = False
        self.history.clear()

    # ----------------------------------------------------------------- warm

    def _warm(self) -> None:
        html_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
        }
        self._client.get(f"{_BASE}/", headers=html_headers, timeout=10.0)
        for k, v in (
            ("5", "1"),
            ("ah", "wt-wt"),
            ("dcs", "1"),
            ("dcm", "3"),
            ("isRecentChatOn", "1"),
        ):
            for dom in (".duck.ai", ".duckduckgo.com"):
                try:
                    self._client.cookies.set(k, v, domain=dom)
                except Exception:
                    pass
        self._client.get(
            f"{_DDG_BASE}/?q=DuckDuckGo+AI+Chat&ia=chat&duckai=1",
            headers=html_headers,
            timeout=10.0,
        )

    # ------------------------------------------------------------ challenge

    def _fetch_challenge_header(self) -> str:
        # Use a cached pending hash if available — avoids a /status call.
        pending = getattr(self, "_pending_hash", None)
        if pending:
            self._pending_hash = None
            return solve_challenge(pending, _UA)
        # No cached hash: hit /status. duck.ai rate-limits this endpoint too,
        # so retry with backoff on 429.
        for attempt in range(3):
            r = self._client.get(
                f"{_BASE}/duckchat/v1/status",
                headers={
                    "Accept": "*/*",
                    "x-vqd-accept": "1",
                    "Cache-Control": "no-store",
                    "Pragma": "no-cache",
                    "Referer": f"{_BASE}/",
                    "Origin": _BASE,
                },
                timeout=self.timeout,
            )
            if r.status_code == 200:
                challenge = r.headers.get("x-vqd-hash-1")
                if not challenge:
                    raise DuckMindError("server did not return x-vqd-hash-1")
                return solve_challenge(challenge, _UA)
            if r.status_code == 429 and attempt < 2:
                delay = 5.0 * (2**attempt) + random.uniform(0, 1.0)
                time.sleep(delay)
                continue
            if r.status_code == 429:
                raise RatelimitError(r.text)
            raise APIError(
                f"status endpoint: {r.status_code}", r.status_code, r.text
            )
        # unreachable
        raise DuckMindError("_fetch_challenge_header failed")

    def _get_jwk(self) -> Dict[str, Any]:
        if self._jwk is None:
            with self._jwk_lock:
                if self._jwk is None:
                    self._jwk = generate_jwk()
        return self._jwk

    # ------------------------------------------------------------- payload

    def _build_payload(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        can_use_tools: bool = True,
        effort: Optional[str] = None,
        web_search: bool = False,
    ) -> Dict[str, Any]:
        m = resolve_model(model or self.model)
        tool_choice: Dict[str, bool] = dict(_TOOL_CHOICE_OFF)
        if web_search and model_supports_web_search(m):
            tool_choice["WebSearch"] = True
        payload: Dict[str, Any] = {
            "model": m,
            "metadata": {"toolChoice": tool_choice},
            "messages": messages,
            "canUseTools": can_use_tools,
        }
        eff = resolve_effort(m, effort if effort is not None else self.effort)
        if eff is not None:
            payload["reasoningEffort"] = eff
        payload["canUseApproxLocation"] = None
        if m != image_gen:
            payload["durableStream"] = {
                "messageId": str(uuid.uuid4()),
                "conversationId": str(uuid.uuid4()),
                "publicKey": self._get_jwk(),
            }
        return payload

    @staticmethod
    def _endpoint_for(model: str) -> str:
        return _IMAGES_PATH if model == image_gen else _CHAT_PATH

    @staticmethod
    def _has_image(messages: List[Dict[str, Any]]) -> bool:
        for m in messages:
            c = m.get("content")
            if isinstance(c, list):
                for p in c:
                    if isinstance(p, dict) and p.get("type") == "image":
                        return True
        return False

    # ----------------------------------------------------- HTTP + SSE

    def _chat_stream(self, payload: Dict[str, Any]):
        hash_header = self._fetch_challenge_header()
        path = self._endpoint_for(payload.get("model", self.model))
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return self._client.stream(
            "POST",
            f"{_BASE}{path}",
            content=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "x-vqd-hash-1": hash_header,
                "x-fe-signals": make_fe_signals(),
                "x-fe-version": self.fe_version,
                "Referer": f"{_BASE}/",
                "Origin": _BASE,
            },
        )

    @staticmethod
    def _raise_for_status(resp: httpx.Response) -> None:
        try:
            resp.read()
            body = resp.text
        except Exception:
            body = ""
        if resp.status_code == 418:
            raise ChallengeError(f"challenge rejected: {body[:200]}")
        if resp.status_code == 429:
            if "ERR_CONVERSATION_LIMIT" in body:
                raise ConversationLimitError(body)
            raise RatelimitError(body)
        raise APIError(
            f"chat failed: HTTP {resp.status_code}", resp.status_code, body
        )

    @staticmethod
    def _iter_sse(resp: httpx.Response) -> Iterator[str]:
        for raw in resp.iter_lines():
            if not raw:
                continue
            if not raw.startswith("data:"):
                continue
            data = raw[5:].lstrip()
            if data:
                yield data

    # ---------------------------------------------------------- retry core

    def _attempt_stream(
        self, payload: Dict[str, Any]
    ) -> Iterator[dict]:
        with self._chat_stream(payload) as resp:
            if resp.status_code != 200:
                self._raise_for_status(resp)
            new_hash = resp.headers.get("x-vqd-hash-1")
            if new_hash:
                self._pending_hash = new_hash
            saw_any = False
            for data in self._iter_sse(resp):
                if data == "[DONE]":
                    return
                if (
                    data.startswith("[CHAT_TITLE")
                    or data.startswith("[LIMIT")
                    or data.startswith("[PING")
                ):
                    continue
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if obj.get("action") == "error":
                    msg = obj.get("type") or obj.get("error") or json.dumps(obj)
                    if obj.get("status") == 429:
                        if msg == "ERR_CONVERSATION_LIMIT":
                            raise ConversationLimitError(msg)
                        raise RatelimitError(msg)
                    if msg in ("ERR_CHALLENGE", "ERR_INVALID_CHALLENGE"):
                        raise ChallengeError(str(msg))
                    raise APIError(str(msg), obj.get("status"), data)
                saw_any = True
                yield obj
            if not saw_any:
                raise APIError("empty stream", 200, "")

    def _stream_with_retry(
        self, payload: Dict[str, Any]
    ) -> Iterator[dict]:
        last_exc: Optional[BaseException] = None
        for attempt in range(self.max_retries):
            yielded = False
            try:
                for item in self._attempt_stream(payload):
                    yielded = True
                    yield item
                return
            except (ChallengeError, httpx.RemoteProtocolError, httpx.ReadError) as e:
                self._pending_hash = None
                if yielded:
                    raise
                last_exc = e
            except APIError as e:
                if e.status_code is None or e.status_code >= 500:
                    if yielded:
                        raise
                    last_exc = e
                else:
                    raise
            except RatelimitError as e:
                if isinstance(e, ConversationLimitError):
                    raise
                if yielded:
                    raise
                last_exc = e
            except httpx.TimeoutException as e:
                if yielded:
                    raise
                last_exc = e
            if attempt < self.max_retries - 1:
                delay = self.backoff_base * (2**attempt) + random.uniform(0, 0.25)
                time.sleep(delay)
        if last_exc is not None:
            raise last_exc
        raise DuckMindError("exhausted retries with no specific error")

    # ----------------------------------------------------------- public API

    def stream(
        self,
        prompt: Union[str, List[Union[str, ImagePart, dict]]],
        *,
        remember: Optional[bool] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        web_search: bool = False,
    ) -> Iterator[str]:
        if remember is None:
            remember = self.history_enabled
        if remember:
            self.history.add_user(prompt)
            messages = self.history.to_messages()
        else:
            messages = [Message(role=Role.User, content=prompt).to_dict()]
        is_mm = self._has_image(messages)
        if model is not None:
            use_model = resolve_model(model)
        elif is_mm:
            from .models import model_supports_vision
            use_model = (
                self.model
                if model_supports_vision(self.model)
                else "gpt-5-mini"
            )
        else:
            use_model = self.model
        if use_model != self.model:
            self._pending_hash = None
        payload = self._build_payload(
            messages,
            model=use_model,
            effort=effort,
            web_search=web_search,
        )
        collected: List[str] = []
        for obj in self._stream_with_retry(payload):
            chunk = obj.get("message") or ""
            if chunk:
                collected.append(chunk)
                yield chunk
        if remember and collected:
            self.history.add_assistant("".join(collected))

    def ask(
        self,
        prompt: Union[str, List[Union[str, ImagePart, dict]]],
        *,
        remember: Optional[bool] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        web_search: bool = False,
    ) -> str:
        return "".join(
            self.stream(
                prompt,
                remember=remember,
                model=model,
                effort=effort,
                web_search=web_search,
            )
        )

    def ask_with_image(
        self,
        prompt: str,
        image: Union[str, bytes, ImagePart],
        *,
        mime_type: str = "image/png",
        remember: Optional[bool] = None,
        model: Optional[str] = None,
        effort: Optional[str] = None,
        web_search: bool = False,
    ) -> str:
        part = self._coerce_image(image, mime_type)
        return self.ask(
            [prompt, part],
            remember=remember,
            model=model,
            effort=effort,
            web_search=web_search,
        )

    @staticmethod
    def _coerce_image(
        image: Union[str, bytes, ImagePart], mime_type: str
    ) -> ImagePart:
        if isinstance(image, ImagePart):
            return image
        if isinstance(image, bytes):
            return ImagePart.from_bytes(image, mime_type=mime_type)
        if isinstance(image, str):
            if image.startswith("data:"):
                return ImagePart(image=image, mime_type=mime_type)
            return ImagePart.from_path(image)
        raise TypeError(f"unsupported image type: {type(image).__name__}")
