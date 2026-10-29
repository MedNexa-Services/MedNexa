"""Security & JWT authentication utilities (Part 5 - Task 5.3).

HS256 JSON Web Tokens and PBKDF2 password hashing, built on the standard library
only. There are deliberately no fallback secrets here: signing and verifying
fail loudly when MEDNEXA_JWT_SECRET is missing or too short, so a misconfigured
server cannot hand out (or accept) tokens that anyone could forge.

Hash a password for MEDNEXA_ADMIN_PASSWORD with:

    uv run python -m app.core.security
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from app.config import get_settings

MIN_SECRET_LENGTH = 32
PBKDF2_ITERATIONS = 600_000  # OWASP 2023 guidance for PBKDF2-HMAC-SHA256
_JWT_HEADER = {"alg": "HS256", "typ": "JWT"}


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(data.encode("ascii") + b"=" * (-len(data) % 4))
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise ValueError("Invalid token encoding") from exc


def _signing_secret() -> bytes:
    secret = get_settings().jwt_secret
    if len(secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"MEDNEXA_JWT_SECRET must be set to at least {MIN_SECRET_LENGTH} random characters"
            " (e.g. `openssl rand -hex 32`)"
        )
    return secret.encode("utf-8")


def _sign(signing_input: bytes) -> bytes:
    return hmac.new(_signing_secret(), signing_input, hashlib.sha256).digest()


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a signed HS256 JWT."""
    settings = get_settings()
    now = datetime.now(UTC)
    expires = now + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    payload = {**data, "iat": int(now.timestamp()), "exp": int(expires.timestamp())}

    segments = [
        _b64url_encode(json.dumps(_JWT_HEADER, separators=(",", ":")).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ]
    segments.append(_b64url_encode(_sign(".".join(segments).encode("ascii"))))
    return ".".join(segments)


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify a token and return its payload.

    Raises ValueError for anything invalid (format, algorithm, signature, missing
    or past expiry) and RuntimeError if the server has no usable signing secret.
    """
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token format")
    header_b64, payload_b64, signature_b64 = parts
    try:
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("Invalid token format") from exc

    expected = _sign(signing_input)  # also enforces the secret requirements
    if not hmac.compare_digest(expected, _b64url_decode(signature_b64)):
        raise ValueError("Invalid token signature")

    try:
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid token encoding") from exc
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise ValueError("Unsupported token algorithm")
    if not isinstance(payload, dict):
        raise ValueError("Invalid token payload")

    expiry = payload.get("exp")
    if isinstance(expiry, bool) or not isinstance(expiry, int | float):
        raise ValueError("Token has no valid expiry")
    if time.time() >= expiry:
        raise ValueError("Token has expired")
    return cast(dict[str, Any], payload)


def hash_password(password: str, iterations: int = PBKDF2_ITERATIONS) -> str:
    """PBKDF2-HMAC-SHA256 hash as `pbkdf2:$<iterations>$<salt hex>$<key hex>`."""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2:${iterations}${salt.hex()}${key.hex()}"


def verify_password(plain_password: str, stored: str) -> bool:
    """Check a password against the configured value.

    `stored` is either a PBKDF2 hash (see hash_password; the legacy
    `pbkdf2:$<salt>$<key>` form with 100,000 iterations is still accepted) or a
    plain password. A stored hash is never accepted as the password itself, and
    an empty stored value never matches.
    """
    if not stored:
        return False
    if not stored.startswith("pbkdf2:"):
        return hmac.compare_digest(plain_password.encode("utf-8"), stored.encode("utf-8"))
    try:
        fields = stored.split("$")[1:]
        if len(fields) == 2:  # legacy: pbkdf2:$salt$key
            iterations, (salt_hex, key_hex) = 100_000, fields
        else:
            iterations, salt_hex, key_hex = int(fields[0]), fields[1], fields[2]
        salt, expected = bytes.fromhex(salt_hex), bytes.fromhex(key_hex)
        if iterations <= 0 or not salt or not expected:
            return False
        derived = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
    except (ValueError, IndexError):
        return False
    return hmac.compare_digest(derived, expected)


if __name__ == "__main__":  # pragma: no cover - operator helper
    import getpass

    entered = getpass.getpass("Password to hash: ")
    if entered != getpass.getpass("Repeat: "):
        raise SystemExit("Passwords do not match")
    print(hash_password(entered))
