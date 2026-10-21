"""Generate ephemeral public parameters for Duck.ai's stream-resumption token."""

import base64
import math
import secrets
import uuid


def _b64u_int(value):
    raw = value.to_bytes((value.bit_length() + 7) // 8 or 1, 'big')
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode()


def _prime(bits):
    while True:
        n = secrets.randbits(bits) | (1 << (bits - 1)) | 1
        if any(n % p == 0 for p in (3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47)):
            continue
        if math.gcd(n - 1, 65537) != 1:
            continue
        d, shifts = n - 1, 0
        while not d & 1:
            d >>= 1
            shifts += 1
        for _ in range(40):
            x = pow(secrets.randbelow(n - 3) + 2, d, n)
            if x in (1, n - 1):
                continue
            for _ in range(shifts - 1):
                x = x * x % n
                if x == n - 1:
                    break
            else:
                break
        else:
            return n


def generate_jwk():
    # This client uses only the public key; no private key is stored or used to decrypt.
    while True:
        p, q = _prime(1024), _prime(1024)
        n = p * q
        if p != q and n.bit_length() == 2048:
            break
    return {'alg': 'RSA-OAEP-256', 'e': _b64u_int(65537), 'ext': True,
            'key_ops': ['encrypt'], 'kty': 'RSA', 'n': _b64u_int(n), 'use': 'enc'}


def make_durable_stream(jwk=None):
    return {'messageId': str(uuid.uuid4()), 'conversationId': str(uuid.uuid4()),
            'publicKey': jwk or generate_jwk()}
