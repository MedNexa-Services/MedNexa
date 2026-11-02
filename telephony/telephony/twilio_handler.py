from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import secrets
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from urllib.parse import quote
from xml.sax.saxutils import escape, quoteattr

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, Response
from twilio.rest import Client

from telephony import capacity
from telephony.api_client import BackendClient
from telephony.audio_codec import pipeline_to_twilio, twilio_to_pipeline
from telephony.config import get_settings
from telephony.logging_setup import get_logger
from telephony.pipeline import CallPipeline

log = get_logger("twilio")

router = APIRouter(prefix="/twilio", tags=["twilio"])


STREAM_TOKEN_TTL_SECONDS = 60.0


@dataclass(frozen=True)
class PendingStream:
    call_sid: str
    caller_phone: str
    issued_at: float


_pending_streams: dict[str, PendingStream] = {}


def _issue_stream_token(call_sid: str, caller_phone: str) -> str:
    now = time.monotonic()
    for token, pending in list(_pending_streams.items()):
        if now - pending.issued_at > STREAM_TOKEN_TTL_SECONDS:
            del _pending_streams[token]
    token = secrets.token_urlsafe(24)
    _pending_streams[token] = PendingStream(call_sid, caller_phone, now)
    return token


def _claim_stream_token(token: str | None, call_sid: str) -> PendingStream | None:
    pending = _pending_streams.pop(token or "", None)
    if pending is None or pending.call_sid != call_sid:
        return None
    if time.monotonic() - pending.issued_at > STREAM_TOKEN_TTL_SECONDS:
        return None
    return pending


def _signature_valid(url: str, params: dict[str, str], signature: str) -> bool:
    from twilio.request_validator import RequestValidator  # type: ignore[import-untyped]

    validator = RequestValidator(get_settings().twilio_auth_token)
    return bool(validator.validate(url, params, signature))


def build_twiml(call_sid: str, public_url: str, caller_phone: str, stream_token: str) -> str:
    ws_url = public_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = ws_url.rstrip("/") + f"/twilio/stream/{quote(call_sid, safe='')}"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url={quoteattr(ws_url)}>
      <Parameter name="call_sid" value={quoteattr(call_sid)}/>
      <Parameter name="caller_phone" value={quoteattr(caller_phone)}/>
      <Parameter name="stream_token" value={quoteattr(stream_token)}/>
    </Stream>
  </Connect>
</Response>"""


async def transfer_to_staff(call_sid: str) -> bool:
    cfg = get_settings()
    if not (cfg.transfer_phone_number and cfg.twilio_account_sid and cfg.twilio_auth_token):
        return False
    twiml = f"<Response><Dial>{escape(cfg.transfer_phone_number)}</Dial></Response>"
    try:
        client = Client(cfg.twilio_account_sid, cfg.twilio_auth_token)
        await asyncio.to_thread(client.calls(call_sid).update, twiml=twiml)
    except Exception:
        log.exception("transfer_failed", call_sid=call_sid)
        return False
    log.info("call_transferred", call_sid=call_sid)
    return True


@router.post("/voice", response_model=None)
async def voice_webhook(request: Request) -> Response:
    form = await request.form()
    params = {key: str(value) for key, value in form.items()}
    cfg = get_settings()

    if cfg.twilio_auth_token:
        url = f"{cfg.public_url.rstrip('/')}/twilio/voice" if cfg.public_url else str(request.url)
        signature = request.headers.get("X-Twilio-Signature", "")
        if not _signature_valid(url, params, signature):
            log.warning("twilio_signature_invalid", url=url)
            return Response(status_code=403)
    else:
        log.warning("twilio_signature_not_checked", reason="MEDNEXA_TEL_TWILIO_AUTH_TOKEN unset")

    call_sid = params.get("CallSid", "unknown")
    caller_phone = params.get("From", "")
    log.info("incoming_call", call_sid=call_sid, caller=caller_phone)

    if capacity.calls.full():
        log.warning("call_refused_busy", call_sid=call_sid, active=capacity.calls.active)
        busy = (
            '<?xml version="1.0" encoding="UTF-8"?><Response><Say>All our lines are busy. '
            "Please call again in a moment.</Say><Hangup/></Response>"
        )
        return PlainTextResponse(content=busy, media_type="text/xml")

    if not cfg.public_url:
        log.error("public_url_not_set")
    token = _issue_stream_token(call_sid, caller_phone)
    twiml = build_twiml(call_sid, cfg.public_url or "http://localhost:8001", caller_phone, token)
    return PlainTextResponse(content=twiml, media_type="text/xml")


@router.websocket("/stream/{call_sid}")
async def stream_websocket(websocket: WebSocket, call_sid: str) -> None:
    await websocket.accept()
    if not capacity.calls.try_acquire():
        await websocket.close(code=1013)
        return
    try:
        await _serve_stream(websocket, call_sid)
    finally:
        capacity.calls.release()


async def _serve_stream(websocket: WebSocket, call_sid: str) -> None:
    cfg = get_settings()
    caller_phone = ""
    stream_sid: str | None = None
    session_id: str | None = None
    rejected = asyncio.Event()
    pipeline: CallPipeline | None = None

    audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)

    async def receive_loop() -> None:
        nonlocal caller_phone, stream_sid, session_id
        try:
            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                event = msg.get("event")

                if event == "start":
                    start = msg.get("start", {})
                    params = start.get("customParameters", {})
                    pending = _claim_stream_token(params.get("stream_token"), call_sid)
                    if pending is None:
                        log.warning("stream_rejected", call_sid=call_sid)
                        rejected.set()
                        return
                    caller_phone = pending.caller_phone
                    stream_sid = start.get("streamSid") or msg.get("streamSid")
                    log.info("stream_started", call_sid=call_sid, caller=caller_phone)

                    async with BackendClient() as client:
                        session_id = await client.start_call(cfg.hospital_id, caller_phone)

                elif event == "media" and stream_sid is not None:
                    payload = msg.get("media", {}).get("payload", "")
                    if pipeline is not None and not pipeline.listening:
                        continue
                    pcm_16k = twilio_to_pipeline(base64.b64decode(payload))
                    if audio_queue.full():
                        audio_queue.get_nowait()
                    audio_queue.put_nowait(pcm_16k)

                elif event == "stop":
                    log.info("stream_stopped", call_sid=call_sid)
                    break

        except WebSocketDisconnect:
            log.info("websocket_disconnected", call_sid=call_sid)
        finally:
            if audio_queue.full():
                audio_queue.get_nowait()
            audio_queue.put_nowait(b"")

    async def audio_generator() -> AsyncIterator[bytes]:
        while True:
            chunk = await audio_queue.get()
            if chunk == b"":
                return
            yield chunk

    async def send_json(message: dict[str, object]) -> None:
        with contextlib.suppress(Exception):
            await websocket.send_text(json.dumps(message))

    async def send_audio(pcm_16k: bytes) -> None:
        payload = base64.b64encode(pipeline_to_twilio(pcm_16k)).decode("ascii")
        await send_json({"event": "media", "streamSid": stream_sid, "media": {"payload": payload}})

    receive_task = asyncio.create_task(receive_loop())
    for _ in range(50):
        await asyncio.sleep(0.1)
        if session_id is not None or rejected.is_set() or receive_task.done():
            break

    if session_id is None:
        log.error("no_session_id", call_sid=call_sid, rejected=rejected.is_set())
        receive_task.cancel()
        with contextlib.suppress(Exception):
            await websocket.close(code=1008)
        return

    async def clear_audio() -> None:
        await send_json({"event": "clear", "streamSid": stream_sid})

    async def transfer() -> bool:
        return await transfer_to_staff(call_sid)

    pipeline = CallPipeline(
        session_id, caller_phone, send_audio, clear_audio=clear_audio, transfer=transfer
    )

    pipeline_task = asyncio.create_task(pipeline.run(audio_generator()))

    done, pending = await asyncio.wait(
        [receive_task, pipeline_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        if not task.cancelled() and task.exception() is not None:
            log.error("stream_task_failed", error=repr(task.exception()))
