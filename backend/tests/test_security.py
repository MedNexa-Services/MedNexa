"""Token and password handling (app/core/security.py)."""

import base64
import hashlib
import hmac
import json
from datetime import timedelta

import pytest

from app.config import get_settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

# The secret the PR originally shipped as a default in config.py and compose.
PUBLISHED_DEFAULT_SECRET = "mednexa-super-secret-jwt-signing-key-32bytes-minimum"


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def forge(payload: dict, secret: str, header: dict | None = None) -> str:
    header_b64 = b64(json.dumps(header or {"alg": "HS256", "typ": "JWT"}).encode())
    body_b64 = b64(json.dumps(payload).encode())
    signature = hmac.new(secret.encode(), f"{header_b64}.{body_b64}".encode(), hashlib.sha256)
    return f"{header_b64}.{body_b64}.{b64(signature.digest())}"


# --- tokens ---------------------------------------------------------------------


def test_token_signed_with_the_published_default_secret_is_rejected() -> None:
    forged = forge({"sub": "attacker@evil.test", "exp": 9999999999}, PUBLISHED_DEFAULT_SECRET)
    with pytest.raises(ValueError, match="signature"):
        decode_access_token(forged)


def test_token_without_expiry_is_rejected() -> None:
    secret = get_settings().jwt_secret
    with pytest.raises(ValueError, match="expir"):
        decode_access_token(forge({"sub": "admin@hospital.com"}, secret))


def test_token_with_a_non_numeric_expiry_is_rejected() -> None:
    secret = get_settings().jwt_secret
    with pytest.raises(ValueError, match="expir"):
        decode_access_token(forge({"sub": "a@b.c", "exp": "never"}, secret))


def test_token_with_another_algorithm_header_is_rejected() -> None:
    secret = get_settings().jwt_secret
    token = forge({"sub": "a@b.c", "exp": 9999999999}, secret, header={"alg": "none"})
    with pytest.raises(ValueError, match="algorithm"):
        decode_access_token(token)


@pytest.mark.parametrize("garbage", ["", "abc", "a.b", "a.b.c.d", "....", "é.é.é"])
def test_malformed_tokens_raise_value_error(garbage: str) -> None:
    with pytest.raises(ValueError):
        decode_access_token(garbage)


def test_secrets_that_are_missing_or_short_cannot_sign_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for weak in ("", "short"):
        monkeypatch.setattr(get_settings(), "jwt_secret", weak)
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            create_access_token({"sub": "a@b.c"})
        with pytest.raises(RuntimeError, match="JWT_SECRET"):
            decode_access_token("a.b.c")


def test_expired_token_is_rejected() -> None:
    token = create_access_token({"sub": "a@b.c"}, expires_delta=timedelta(seconds=-5))
    with pytest.raises(ValueError, match="expired"):
        decode_access_token(token)


# --- passwords ------------------------------------------------------------------


def test_the_stored_hash_cannot_be_used_as_the_password() -> None:
    stored = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", stored)
    assert not verify_password(stored, stored)  # logging in with the leaked hash itself


def test_hashes_are_salted_and_record_their_cost() -> None:
    a, b = hash_password("same"), hash_password("same")
    assert a != b
    assert verify_password("same", a) and verify_password("same", b)
    assert a.startswith("pbkdf2:$") and a.split("$")[1].isdigit()
    assert int(a.split("$")[1]) >= 600_000


def test_legacy_three_part_hashes_still_verify() -> None:
    salt = b"0123456789abcdef"
    key = hashlib.pbkdf2_hmac("sha256", b"old-password", salt, 100_000).hex()
    assert verify_password("old-password", f"pbkdf2:${salt.hex()}${key}")


@pytest.mark.parametrize(
    "stored, attempt",
    [("", ""), ("", "anything"), ("pbkdf2:", "x"), ("pbkdf2:$$", "x"), ("pbkdf2:$abc$zz$yy", "x")],
)
def test_empty_or_corrupt_stored_values_never_match(stored: str, attempt: str) -> None:
    assert not verify_password(attempt, stored)


def test_plain_configured_password_still_works_and_is_case_sensitive() -> None:
    assert verify_password("S3cret!", "S3cret!")
    assert not verify_password("s3cret!", "S3cret!")
