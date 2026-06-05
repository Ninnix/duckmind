"""
Generate RSA-OAEP public keys for durable streams.

DuckDuckGo's chat endpoint uses durable streams — persistent SSE connections
that survive brief network hiccups. The initial POST must carry a JWK public
key so the server can encrypt the stream-resumption token.

We generate a fresh 2048-bit RSA key pair per client instance. Only the
public half is sent; the private half is kept in memory and never persisted.
"""

from __future__ import annotations

import base64
import uuid
from typing import Any, Dict, Optional

from .exceptions import DuckMindError


def _b64u_int(i: int) -> str:
    length = (i.bit_length() + 7) // 8 or 1
    return base64.urlsafe_b64encode(i.to_bytes(length, "big")).rstrip(b"=").decode()


def generate_jwk() -> Dict[str, Any]:
    try:
        from cryptography.hazmat.primitives.asymmetric import rsa
    except ImportError as e:
        raise DuckMindError(
            "duck.ai requires a real RSA-OAEP public key for durable streams. "
            "Install: pip install cryptography"
        ) from e
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nums = key.public_key().public_numbers()
    return {
        "alg": "RSA-OAEP-256",
        "e": _b64u_int(nums.e),
        "ext": True,
        "key_ops": ["encrypt"],
        "kty": "RSA",
        "n": _b64u_int(nums.n),
        "use": "enc",
    }


def make_durable_stream(jwk: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {
        "messageId": str(uuid.uuid4()),
        "conversationId": str(uuid.uuid4()),
        "publicKey": jwk or generate_jwk(),
    }
