"""Twilio telephony integration — webhook server for prototype mode.

Implements the Twilio Programmable Voice + Media Streams flow:

  1. Twilio receives a call and hits POST /twilio/voice
     → We respond with TwiML that connects a <Stream> to our WebSocket.

  2. Twilio opens a WebSocket to GET /twilio/stream/{call_sid}
     → We create a CallPipeline and run it, bridging Twilio audio
       bytes to the pipeline's audio stream.

  3. The pipeline runs until the call ends, then the WebSocket closes.

Audio format from Twilio Media Streams:
  - mulaw (μ-law) encoded, 8 kHz, mono, base64-encoded JSON messages.
  - Converted to/from the pipeline's 16 kHz PCM by telephony.audio_codec.

Reference:
  https://www.twilio.com/docs/voice/tutorials/consume-real-time-media-stream-using-websockets-python-and-flask
"""

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
from xml.sax.saxutils import quoteattr

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, Response

from telephony.api_client import BackendClient
from telephony.audio_codec import pipeline_to_twilio, twilio_to_pipeline
from telephony.config import get_settings
from telephony.logging_setup import get_logger
from telephony.pipeline import CallPipeline

log = get_logger("twilio")

router = APIRouter(prefix="/twilio", tags=["twilio"])

# ── Stream authorisation ───────────────────────────────────────────────────────
#
# The voice webhook is signed by Twilio (validated below). It hands out a one-time
# token inside the TwiML; the media WebSocket must present it in the stream's
# "start" message. The caller's number is taken from the signed webhook, never
# from the WebSocket, so a client that opens the socket directly gets nothing.

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
    """Single use: the token is removed whether or not it is still valid."""
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


# ── TwiML response ─────────────────────────────────────────────────────────────


def build_twiml(call_sid: str, public_url: str, caller_phone: str, stream_token: str) -> str:
    """Return TwiML that connects the call to our WebSocket stream."""
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


# ── Webhook endpoints ──────────────────────────────────────────────────────────


@router.post("/voice", response_model=None)
async def voice_webhook(request: Request) -> Response:
    """Twilio calls this endpoint when an incoming call arrives.

    We respond with TwiML to start a bidirectional Media Stream. When an auth
    token is configured, requests without a valid X-Twilio-Signature are refused.
    """
    form = await request.form()
    params = {key: str(value) for key, value in form.items()}
    cfg = get_settings()

    if cfg.twilio_auth_token:
        # Twilio signs the exact URL it was configured with (the public one).
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

    if not cfg.public_url:
        log.error("public_url_not_set")
        # Still respond with TwiML to avoid Twilio retry loops
    token = _issue_stream_token(call_sid, caller_phone)
    twiml = build_twiml(call_sid, cfg.public_url or "http://localhost:8001", caller_phone, token)
    return PlainTextResponse(content=twiml, media_type="text/xml")


@router.websocket("/stream/{call_sid}")
async def stream_websocket(websocket: WebSocket, call_sid: str) -> None:
    """Twilio Media Streams WebSocket.

    Twilio sends JSON messages over this socket:
      - connected: stream started
      - start:     stream metadata (streamSid, our custom parameters)
      - media:     audio payload (base64 μ-law, 8 kHz)
      - stop:      caller hung up

    We bridge this to a ``CallPipeline`` by:
      - Converting Twilio μ-law audio → 16 kHz PCM for the pipeline.
      - Converting pipeline TTS output (16 kHz PCM) → 8 kHz μ-law for Twilio,
        addressed to the stream's streamSid.
    """
    await websocket.accept()
    cfg = get_settings()
    caller_phone = ""
    stream_sid: str | None = None
    session_id: str | None = None
    rejected = asyncio.Event()

    # Audio queue: pipeline reads from this
    audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)

    async def receive_loop() -> None:
        """Read Twilio messages and push audio into the queue."""
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

                    # Create call session in backend
                    async with BackendClient() as client:
                        session_id = await client.start_call(cfg.hospital_id, caller_phone)

                elif event == "media" and stream_sid is not None:
                    payload = msg.get("media", {}).get("payload", "")
                    pcm_16k = twilio_to_pipeline(base64.b64decode(payload))
                    if audio_queue.full():  # drop the oldest chunk rather than stall
                        audio_queue.get_nowait()
                    audio_queue.put_nowait(pcm_16k)

                elif event == "stop":
                    log.info("stream_stopped", call_sid=call_sid)
                    await audio_queue.put(b"")  # sentinel
                    break

        except WebSocketDisconnect:
            log.info("websocket_disconnected", call_sid=call_sid)
            await audio_queue.put(b"")

    async def audio_generator() -> AsyncIterator[bytes]:
        """Convert the queue to an async iterator for the pipeline."""
        while True:
            chunk = await audio_queue.get()
            if chunk == b"":
                return
            yield chunk

    async def send_json(message: dict[str, object]) -> None:
        with contextlib.suppress(Exception):  # connection may have closed
            await websocket.send_text(json.dumps(message))

    async def send_audio(pcm_16k: bytes) -> None:
        """Send TTS audio back to Twilio (PCM → μ-law → base64 JSON)."""
        payload = base64.b64encode(pipeline_to_twilio(pcm_16k)).decode("ascii")
        await send_json({"event": "media", "streamSid": stream_sid, "media": {"payload": payload}})

    # Wait until we have a session_id before starting the pipeline
    receive_task = asyncio.create_task(receive_loop())
    # Give the receive loop time to get the "start" message
    for _ in range(50):  # up to 5 seconds
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
        """Make Twilio discard audio it has buffered but not yet played (barge-in)."""
        await send_json({"event": "clear", "streamSid": stream_sid})

    pipeline = CallPipeline(session_id, caller_phone, send_audio, clear_audio=clear_audio)

    pipeline_task = asyncio.create_task(pipeline.run(audio_generator()))

    # Wait for both to complete
    done, pending = await asyncio.wait(
        [receive_task, pipeline_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
