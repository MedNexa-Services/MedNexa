from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.main import create_app


def test_password_hashing():
    raw = "admin123"
    hashed = hash_password(raw)
    assert hashed.startswith("pbkdf2:")
    assert verify_password(raw, hashed)
    assert not verify_password("wrongpassword", hashed)


def test_jwt_token_encode_decode():
    data = {"sub": "doctor@hospital.com", "role": "Doctor", "name": "Dr. Strange"}
    token = create_access_token(data, expires_delta=timedelta(minutes=30))
    payload = decode_access_token(token)
    assert payload["sub"] == "doctor@hospital.com"
    assert payload["role"] == "Doctor"
    assert payload["name"] == "Dr. Strange"
    assert "exp" in payload


def test_jwt_expired_token():
    data = {"sub": "test@hospital.com"}
    expired_token = create_access_token(data, expires_delta=timedelta(seconds=-10))
    with pytest.raises(ValueError, match="expired"):
        decode_access_token(expired_token)


def test_jwt_tampered_token():
    token = create_access_token({"sub": "admin@hospital.com"})
    parts = token.split(".")
    tampered = f"{parts[0]}.{parts[1]}.tamperedsig"
    with pytest.raises(ValueError, match="signature"):
        decode_access_token(tampered)


async def test_auth_login_success(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@hospital.com", "password": "admin123"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@hospital.com"
    assert data["user"]["name"] == "Dr. Admin"


async def test_auth_login_invalid_password(client: AsyncClient):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@hospital.com", "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert "Incorrect email or password" in response.json()["detail"]


async def test_auth_me_with_real_unoverridden_dependency():
    """Test require_staff dependency directly on an app without overrides."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Without token -> 401
        res = await c.get("/api/v1/auth/me")
        assert res.status_code == 401

        # With invalid token -> 401
        res_bad = await c.get("/api/v1/auth/me", headers={"Authorization": "Bearer badtoken"})
        assert res_bad.status_code == 401

        # Login to get valid token
        login_res = await c.post(
            "/api/v1/auth/login",
            json={"email": "admin@hospital.com", "password": "admin123"},
        )
        assert login_res.status_code == 200
        token = login_res.json()["access_token"]

        # With valid token -> 200
        res_ok = await c.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res_ok.status_code == 200
        assert res_ok.json()["email"] == "admin@hospital.com"
