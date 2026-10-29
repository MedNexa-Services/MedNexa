"""Security & JWT authentication utilities (Part 5 - Task 5.3).

Provides token generation, verification, and password hashing for hospital staff.
Uses standard HS256 JWT formatting with zero required external binary dependencies.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = 4 - (len(data) % 4)
    if padding and padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data.encode("ascii"))


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed HS256 JWT token."""
    try:
        from app.config import get_settings
        settings = get_settings()
        secret = settings.jwt_secret
        expire_minutes = settings.jwt_access_token_expire_minutes
    except Exception:
        secret = "mednexa-super-secret-jwt-signing-key-32bytes-minimum"
        expire_minutes = 120

    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=expire_minutes)

    payload = dict(data)
    payload.update({
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    })

    # Header
    header = {"alg": "HS256", "typ": "JWT"}
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    segments = [
        _b64url_encode(header_bytes),
        _b64url_encode(payload_bytes),
    ]
    signing_input = ".".join(segments).encode("ascii")

    # Signature
    signature = hmac.new(
        secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()

    segments.append(_b64url_encode(signature))
    return ".".join(segments)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a signed HS256 JWT token.

    Raises ValueError if invalid, expired, or signature does not match.
    """
    try:
        from app.config import get_settings
        secret = get_settings().jwt_secret
    except Exception:
        secret = "mednexa-super-secret-jwt-signing-key-32bytes-minimum"
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")

    header_b64, payload_b64, signature_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()

    actual_sig = _b64url_decode(signature_b64)
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Invalid token signature")

    payload_bytes = _b64url_decode(payload_b64)
    payload = json.loads(payload_bytes.decode("utf-8"))

    exp = payload.get("exp")
    if exp and time.time() > float(exp):
        raise ValueError("Token has expired")

    return payload


def verify_password(plain_password: str, hashed_or_demo: str) -> bool:
    """Verify password against hashed string or plain configured credential."""
    if plain_password == hashed_or_demo:
        return True

    # PBKDF2 hash verification
    if hashed_or_demo.startswith("pbkdf2:"):
        try:
            _, salt_hex, key_hex = hashed_or_demo.split("$")
            salt = bytes.fromhex(salt_hex)
            derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, 100_000)
            return hmac.compare_digest(derived.hex(), key_hex)
        except Exception:
            return False

    return False


def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC-SHA256."""
    import secrets

    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"pbkdf2:${salt.hex()}${derived.hex()}"
