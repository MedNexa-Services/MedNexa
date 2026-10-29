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


# --- everything below runs against the real auth dependencies (no overrides) ----------

from collections.abc import AsyncIterator  # noqa: E402

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker  # noqa: E402

from app.api.deps import get_db  # noqa: E402
from app.config import Settings, get_settings  # noqa: E402
from app.main import lifespan  # noqa: E402
from tests.api.helpers import HOSPITAL  # noqa: E402

LOGIN = "/api/v1/auth/login"
GOOD = {"email": "admin@hospital.com", "password": "admin123"}


@pytest.fixture
async def anon(session_factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    """A client whose requests go through the real require_staff dependencies."""
    app = create_app()

    async def _db() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def token_for(c: AsyncClient) -> dict[str, str]:
    res = await c.post(LOGIN, json=GOOD)
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


async def test_every_protected_route_needs_a_token(anon: AsyncClient) -> None:
    for method, path in [
        ("GET", "/api/v1/hospitals"),
        ("GET", "/api/v1/doctors"),
        ("GET", "/api/v1/patients"),
        ("GET", "/api/v1/appointments"),
        ("GET", "/api/v1/calls"),
        ("POST", "/api/v1/appointments"),
    ]:
        assert (await anon.request(method, path)).status_code == 401, (method, path)
    assert (await anon.get("/api/v1/health")).status_code == 200  # stays public


async def test_staff_token_unlocks_the_api(anon: AsyncClient) -> None:
    headers = await token_for(anon)
    assert (await anon.get("/api/v1/hospitals", headers=headers)).status_code == 200


async def test_repeated_wrong_passwords_are_throttled(anon: AsyncClient) -> None:
    wrong = {"email": "admin@hospital.com", "password": "nope"}
    for _ in range(5):
        assert (await anon.post(LOGIN, json=wrong)).status_code == 401
    blocked = await anon.post(LOGIN, json=wrong)
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0
    # even the correct password waits out the lockout for that account...
    assert (await anon.post(LOGIN, json=GOOD)).status_code == 429
    # ...while other accounts are unaffected
    other = await anon.post(LOGIN, json={"email": "someone@hospital.org", "password": "x"})
    assert other.status_code == 401


async def test_successful_login_clears_the_failure_count(anon: AsyncClient) -> None:
    wrong = {"email": "admin@hospital.com", "password": "nope"}
    for _ in range(4):
        await anon.post(LOGIN, json=wrong)
    assert (await anon.post(LOGIN, json=GOOD)).status_code == 200
    for _ in range(4):
        assert (await anon.post(LOGIN, json=wrong)).status_code == 401


async def test_login_is_unavailable_until_credentials_are_configured(
    anon: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "admin_password", "")
    assert (await anon.post(LOGIN, json={**GOOD, "password": ""})).status_code == 503


async def test_a_server_without_a_signing_secret_accepts_no_token(
    anon: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = await token_for(anon)
    monkeypatch.setattr(get_settings(), "jwt_secret", "")
    assert (await anon.get("/api/v1/hospitals", headers=headers)).status_code == 503


# --- service key (telephony) ---------------------------------------------------------


def service_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_settings().service_api_key}"}


async def test_service_key_can_write_call_logs(anon: AsyncClient) -> None:
    hospital = await anon.post("/api/v1/hospitals", json=HOSPITAL, headers=await token_for(anon))
    started = await anon.post(
        "/api/v1/calls",
        json={"hospital_id": hospital.json()["id"], "caller_phone": "9876543210"},
        headers=service_headers(),
    )
    assert started.status_code == 201
    call_id = started.json()["id"]
    log = await anon.post(
        f"/api/v1/calls/{call_id}/logs",
        json={"role": "USER", "content": "hello"},
        headers=service_headers(),
    )
    assert log.status_code == 201
    ended = await anon.post(
        f"/api/v1/calls/{call_id}/end", json={"call_outcome": "OTHER"}, headers=service_headers()
    )
    assert ended.status_code == 200


async def test_service_key_opens_nothing_else(anon: AsyncClient) -> None:
    for method, path in [
        ("GET", "/api/v1/hospitals"),
        ("GET", "/api/v1/patients"),
        ("GET", "/api/v1/appointments"),
        ("GET", "/api/v1/auth/me"),
    ]:
        res = await anon.request(method, path, headers=service_headers())
        assert res.status_code == 401, (method, path)


async def test_wrong_or_disabled_service_key_is_rejected(
    anon: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    bad = {"Authorization": "Bearer not-the-key"}
    assert (await anon.get("/api/v1/calls", headers=bad)).status_code == 401
    monkeypatch.setattr(get_settings(), "service_api_key", "")
    assert (
        await anon.get("/api/v1/calls", headers={"Authorization": "Bearer "})
    ).status_code == 401


# --- startup validation -------------------------------------------------------------


def test_unusable_auth_configuration_is_listed_in_full() -> None:
    with pytest.raises(RuntimeError) as err:
        Settings(
            _env_file=None, jwt_secret="short", admin_email="", admin_password=""
        ).require_auth_config()
    message = str(err.value)
    assert "MEDNEXA_JWT_SECRET" in message
    assert "MEDNEXA_ADMIN_EMAIL" in message and "MEDNEXA_ADMIN_PASSWORD" in message


def test_valid_or_disabled_auth_configuration_passes() -> None:
    get_settings().require_auth_config()
    Settings(_env_file=None, auth_enabled=False).require_auth_config()  # explicit dev mode


async def test_server_refuses_to_start_without_a_signing_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "jwt_secret", "")
    with pytest.raises(RuntimeError, match="MEDNEXA_JWT_SECRET"):
        async with lifespan(create_app()):
            pass


# --- correlation ids ---------------------------------------------------------------


async def test_safe_correlation_id_is_echoed_and_unsafe_one_replaced(anon: AsyncClient) -> None:
    ok = await anon.get("/api/v1/health", headers={"X-Correlation-ID": "req-123.abc_DEF"})
    assert ok.headers["X-Correlation-ID"] == "req-123.abc_DEF"
    for bad in ["x" * 200, "has spaces", "<script>", "a;b"]:
        res = await anon.get("/api/v1/health", headers={"X-Correlation-ID": bad})
        assert res.headers["X-Correlation-ID"] != bad
        assert len(res.headers["X-Correlation-ID"]) == 36  # a fresh UUID
