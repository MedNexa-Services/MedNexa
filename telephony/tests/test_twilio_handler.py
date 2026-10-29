"""Twilio webhook + Media Streams handler: request validation, TwiML and stream SIDs."""

from __future__ import annotations

import base64
import json
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

import telephony.config as cfg_module
from telephony import twilio_handler

PUBLIC_URL = "https://example.ngrok.app"
AUTH_TOKEN = "test-auth-token"
FORM = {"CallSid": "CA123", "From": "+919876543210", "To": "+14155550100"}


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    settings = cfg_module.get_settings()
    monkeypatch.setattr(settings, "public_url", PUBLIC_URL)
    monkeypatch.setattr(settings, "twilio_auth_token", AUTH_TOKEN)
    twilio_handler._pending_streams.clear()
    app = FastAPI()
    app.include_router(twilio_handler.router)
    return TestClient(app)


def signed_post(client: TestClient, form: dict[str, str], token: str = AUTH_TOKEN) -> Any:
    signature = RequestValidator(token).compute_signature(f"{PUBLIC_URL}/twilio/voice", form)
    return client.post("/twilio/voice", data=form, headers={"X-Twilio-Signature": signature})


def stream_token_from(twiml: str) -> str:
    match = re.search(r'name="stream_token" value="([^"]+)"', twiml)
    assert match, twiml
    return match.group(1)


# ── webhook ───────────────────────────────────────────────────────────────────


def test_unsigned_webhook_is_refused(client: TestClient) -> None:
    assert client.post("/twilio/voice", data=FORM).status_code == 403


def test_wrongly_signed_webhook_is_refused(client: TestClient) -> None:
    assert signed_post(client, FORM, token="someone-else").status_code == 403


def test_signed_webhook_returns_stream_twiml(client: TestClient) -> None:
    response = signed_post(client, FORM)
    assert response.status_code == 200
    twiml = response.text
    assert 'url="wss://example.ngrok.app/twilio/stream/CA123"' in twiml
    assert 'name="caller_phone" value="+919876543210"' in twiml
    assert stream_token_from(twiml) in twilio_handler._pending_streams


def test_twiml_values_are_xml_escaped(client: TestClient) -> None:
    twiml = signed_post(client, {**FORM, "From": '"/><Hangup/><x a="'}).text
    assert "<Hangup/>" not in twiml
    assert "&lt;Hangup/&gt;" in twiml


def test_webhook_is_open_when_no_auth_token_is_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cfg_module.get_settings(), "twilio_auth_token", "")
    assert client.post("/twilio/voice", data=FORM).status_code == 200


# ── media stream ──────────────────────────────────────────────────────────────


@pytest.fixture()
def fake_backend(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    backend = AsyncMock()
    backend.__aenter__.return_value = backend
    backend.start_call.return_value = "session-1"
    monkeypatch.setattr(twilio_handler, "BackendClient", lambda: backend)
    return backend


@pytest.fixture()
def fake_pipeline(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """A pipeline that plays one chunk of audio and then ends the call."""
    created = MagicMock()

    class Pipeline:
        def __init__(self, session_id: str, caller_phone: str, send_audio: Any, **kw: Any):
            created(session_id, caller_phone)
            self.send_audio = send_audio

        async def run(self, audio: Any) -> None:
            await self.send_audio(b"\x00\x10" * 160)

    monkeypatch.setattr(twilio_handler, "CallPipeline", Pipeline)
    return created


def start_message(token: str) -> str:
    return json.dumps({
        "event": "start",
        "streamSid": "MZ999",
        "start": {"streamSid": "MZ999", "callSid": "CA123",
                  "customParameters": {"stream_token": token, "caller_phone": "+910000000000"}},
    })  # fmt: skip


def test_stream_with_valid_token_uses_stream_sid_and_signed_caller(
    client: TestClient, fake_backend: AsyncMock, fake_pipeline: MagicMock
) -> None:
    token = stream_token_from(signed_post(client, FORM).text)
    with client.websocket_connect("/twilio/stream/CA123") as ws:
        ws.send_text(start_message(token))
        outbound = json.loads(ws.receive_text())

    assert outbound["event"] == "media"
    assert outbound["streamSid"] == "MZ999"  # not the call SID
    assert len(base64.b64decode(outbound["media"]["payload"])) == 80  # 160 samples @16k -> 80 @8k
    # The caller number comes from the signed webhook, not the stream parameters.
    fake_backend.start_call.assert_awaited_once()
    assert fake_backend.start_call.await_args.args[1] == "+919876543210"
    fake_pipeline.assert_called_once_with("session-1", "+919876543210")
    assert token not in twilio_handler._pending_streams  # single use


@pytest.mark.parametrize("token", ["forged-token", None])
def test_stream_without_valid_token_is_closed(
    client: TestClient, fake_backend: AsyncMock, fake_pipeline: MagicMock, token: str | None
) -> None:
    with client.websocket_connect("/twilio/stream/CA123") as ws:
        ws.send_text(start_message(token or ""))
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
    fake_backend.start_call.assert_not_awaited()
    fake_pipeline.assert_not_called()


def test_token_is_bound_to_its_call(
    client: TestClient, fake_backend: AsyncMock, fake_pipeline: MagicMock
) -> None:
    token = stream_token_from(signed_post(client, FORM).text)
    with client.websocket_connect("/twilio/stream/CA-OTHER") as ws:
        ws.send_text(start_message(token))
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()
    fake_pipeline.assert_not_called()
