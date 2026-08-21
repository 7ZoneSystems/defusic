"""Authenticated encryption for Drive tokens at rest.

Uses AES-256-GCM (AEAD). Encrypted values are stored as:
    v1:<base64(nonce)><base64(ciphertext)><base64(tag)>

The nonce (12 bytes) is random per encryption operation.
The 16-byte GCM tag provides authentication.

Requires DRIVE_TOKEN_ENCRYPTION_KEY env var (base64-encoded 32 bytes).
"""

from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Nonce length for AES-GCM (96 bits / 12 bytes recommended)
_NONCE_LEN = 12
_VERSION = "v1"


def _get_key() -> bytes:
    """Load the encryption key from environment. Raises on missing/malformed."""
    raw = os.getenv("DRIVE_TOKEN_ENCRYPTION_KEY", "")
    if not raw:
        raise RuntimeError(
            "DRIVE_TOKEN_ENCRYPTION_KEY not set. "
            "Generate one with: python -c \"import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())\""
        )
    try:
        key = base64.b64decode(raw)
    except Exception as exc:
        raise RuntimeError("DRIVE_TOKEN_ENCRYPTION_KEY is not valid base64") from exc
    if len(key) != 32:
        raise RuntimeError(
            f"DRIVE_TOKEN_ENCRYPTION_KEY must be 32 bytes (got {len(key)})"
        )
    return key


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token string. Returns v1:<encoded>."""
    key = _get_key()
    nonce = os.urandom(_NONCE_LEN)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    # ct includes the 16-byte GCM tag appended
    encoded = base64.b64encode(nonce + ct).decode("ascii")
    return f"{_VERSION}:{encoded}"


def decrypt_token(token: str) -> str:
    """Decrypt a token string. Accepts v1:<encoded> or raw plaintext (legacy).

    If the value does not start with 'v1:', it is treated as legacy
    plaintext and returned as-is. The caller should then encrypt and
    re-persist it.
    """
    if not token:
        return token

    if not token.startswith(f"{_VERSION}:"):
        # Legacy plaintext — return as-is for migration
        return token

    key = _get_key()
    encoded = token[len(_VERSION) + 1 :]
    try:
        raw = base64.b64decode(encoded)
    except Exception as exc:
        raise RuntimeError("Malformed encrypted token") from exc

    if len(raw) < _NONCE_LEN + 16:
        raise RuntimeError("Encrypted token too short")

    nonce = raw[:_NONCE_LEN]
    ct = raw[_NONCE_LEN:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ct, None)
    return plaintext.decode("utf-8")


def is_encrypted(value: str | None) -> bool:
    """Check if a value is in encrypted v1 format."""
    return bool(value and value.startswith(f"{_VERSION}:"))
