"""Tests for Drive token encryption at rest (AES-256-GCM)."""

import base64
import os
import secrets

import pytest

from hearbeat.token_encryption import (
    encrypt_token,
    decrypt_token,
    is_encrypted,
    _get_key,
)


# --- Key setup ---


@pytest.fixture(autouse=True)
def set_encryption_key(monkeypatch):
    """Set a consistent test encryption key."""
    key = base64.b64encode(secrets.token_bytes(32)).decode()
    monkeypatch.setenv("DRIVE_TOKEN_ENCRYPTION_KEY", key)
    return key


# --- Round trip ---


def test_encrypt_decrypt_roundtrip():
    plaintext = "ya29.a0AfH6SMBx+example_access_token_12345"
    encrypted = encrypt_token(plaintext)
    decrypted = decrypt_token(encrypted)
    assert decrypted == plaintext


def test_encrypt_decrypt_roundtrip_various_values():
    for value in [
        "short",
        "a" * 500,
        "unicode: \u00e9\u00e8\u00ea",
        "special: !@#$%^&*()",
        "",
    ]:
        if not value:
            continue
        encrypted = encrypt_token(value)
        assert decrypt_token(encrypted) == value


# --- Format checks ---


def test_encrypted_format_starts_with_v1():
    encrypted = encrypt_token("test")
    assert encrypted.startswith("v1:")


def test_encrypted_value_is_base64_after_prefix():
    encrypted = encrypt_token("test")
    encoded = encrypted[3:]  # strip "v1:"
    # Should be valid base64
    raw = base64.b64decode(encoded)
    # Raw should be at least 12 (nonce) + 16 (tag) = 28 bytes
    assert len(raw) >= 28


def test_is_encrypted_detects_v1():
    assert is_encrypted("v1:abc123") is True
    assert is_encrypted("plaintext_token") is False
    assert is_encrypted(None) is False
    assert is_encrypted("") is False


# --- Unique nonce per encryption ---


def test_unique_nonces_per_encryption():
    plaintext = "same_token_value"
    enc1 = encrypt_token(plaintext)
    enc2 = encrypt_token(plaintext)
    # Encrypted values must differ (different random nonces)
    assert enc1 != enc2
    # But both must decrypt correctly
    assert decrypt_token(enc1) == plaintext
    assert decrypt_token(enc2) == plaintext


# --- Wrong key fails ---


def test_wrong_key_fails(monkeypatch):
    key1 = base64.b64encode(secrets.token_bytes(32)).decode()
    key2 = base64.b64encode(secrets.token_bytes(32)).decode()

    monkeypatch.setenv("DRIVE_TOKEN_ENCRYPTION_KEY", key1)
    encrypted = encrypt_token("secret")

    monkeypatch.setenv("DRIVE_TOKEN_ENCRYPTION_KEY", key2)
    with pytest.raises(Exception):
        decrypt_token(encrypted)


# --- Tampered ciphertext fails ---


def test_tampered_ciphertext_fails():
    encrypted = encrypt_token("secret")
    encoded = encrypted[3:]  # strip "v1:"
    raw = bytearray(base64.b64decode(encoded))
    # Flip a bit in the ciphertext (after the 12-byte nonce)
    raw[14] ^= 0x01
    tampered = "v1:" + base64.b64encode(bytes(raw)).decode()
    with pytest.raises(Exception):
        decrypt_token(tampered)


def test_tampered_tag_fails():
    encrypted = encrypt_token("secret")
    encoded = encrypted[3:]
    raw = bytearray(base64.b64decode(encoded))
    # Flip a bit in the GCM tag (last byte)
    raw[-1] ^= 0x01
    tampered = "v1:" + base64.b64encode(bytes(raw)).decode()
    with pytest.raises(Exception):
        decrypt_token(tampered)


# --- Legacy plaintext migration ---


def test_legacy_plaintext_passthrough():
    """Legacy plaintext tokens are returned as-is for migration."""
    legacy = "ya29 legacy_access_token"
    assert decrypt_token(legacy) == legacy
    assert is_encrypted(legacy) is False


# --- Missing key behavior ---


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("DRIVE_TOKEN_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DRIVE_TOKEN_ENCRYPTION_KEY not set"):
        encrypt_token("test")


def test_missing_key_decrypt_raises(monkeypatch):
    monkeypatch.delenv("DRIVE_TOKEN_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="DRIVE_TOKEN_ENCRYPTION_KEY not set"):
        decrypt_token("v1:abc")


# --- Malformed encrypted value ---


def test_malformed_base64_fails():
    with pytest.raises(RuntimeError, match="Malformed"):
        decrypt_token("v1:!!!not-base64!!!")


def test_too_short_ciphertext_fails():
    # Valid base64 but too short (less than 12 nonce + 16 tag)
    short = base64.b64encode(b"tooshort").decode()
    with pytest.raises(RuntimeError, match="too short"):
        decrypt_token(f"v1:{short}")


# --- Empty / None handling ---


def test_empty_string_returns_empty():
    assert decrypt_token("") == ""


def test_none_returns_none():
    assert decrypt_token(None) is None
