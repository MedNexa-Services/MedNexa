"""BackendClient: authentication header and request shape."""

from __future__ import annotations

import httpx
import pytest

import telephony.config as cfg_module
from telephony.api_client import BackendClient


def client_with(
    monkeypatch: pytest.MonkeyPatch, key: str
) -> tuple[BackendClient, list[httpx.Request]]:
    monkeypatch.setattr(cfg_module.get_settings(), "backend_api_key", key)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json={"id": "session-1"})

    client = BackendClient(base_url="http://backend")
    client._client._transport = httpx.MockTransport(handler)
    return client, seen


@pytest.mark.asyncio
async def test_service_key_is_sent_as_a_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    client, seen = client_with(monkeypatch, "k" * 40)
    assert await client.start_call("hosp-1", "+919876543210") == "session-1"
    assert seen[0].headers["Authorization"] == f"Bearer {'k' * 40}"
    assert seen[0].url.path == "/api/v1/calls"
    await client.aclose()


@pytest.mark.asyncio
async def test_no_authorization_header_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    client, seen = client_with(monkeypatch, "")
    await client.start_call("hosp-1", "+919876543210")
    assert "Authorization" not in seen[0].headers
    await client.aclose()


@pytest.mark.asyncio
async def test_health_check_reports_reachability(monkeypatch: pytest.MonkeyPatch) -> None:
    client, _ = client_with(monkeypatch, "")
    client._client._transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    assert await client.health_check() is True
    client._client._transport = httpx.MockTransport(lambda r: httpx.Response(503))
    assert await client.health_check() is False
    await client.aclose()
