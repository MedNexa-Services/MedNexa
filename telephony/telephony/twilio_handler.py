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
  - We decode μ-law → linear PCM, then upsample 8 kHz → 16 kHz for Whisper.

Reference:
  https://www.twilio.com/docs/voice/tutorials/consume-real-time-media-stream-using-websockets-python-and-flask
"""

from __future__ import annotations

import asyncio
import base64
import json
import struct
from typing import AsyncIterator

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse

from telephony.agent_interface import AgentInterface, StubAgent
from telephony.api_client import BackendClient
from telephony.config import get_settings
from telephony.logging_setup import get_logger
from telephony.pipeline import CallPipeline

log = get_logger("twilio")

router = APIRouter(prefix="/twilio", tags=["twilio"])

from telephony.tts import (
    pcm_16k_to_ulaw_8k,
    ulaw_to_linear,
    upsample_8k_to_16k,
)

# ── TwiML response ─────────────────────────────────────────────────────────────


def build_twiml(call_sid: str, public_url: str) -> str:
    """Return TwiML that connects the call to our WebSocket stream."""
    ws_url = public_url.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = ws_url.rstrip("/") + f"/twilio/stream/{call_sid}"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{ws_url}">
      <Parameter name="call_sid" value="{call_sid}"/>
    </Stream>
  </Connect>
</Response>"""


# ── Webhook endpoints ──────────────────────────────────────────────────────────


@router.post("/voice")
async def voice_webhook(request: Request) -> PlainTextResponse:
    """Twilio calls this endpoint when an incoming call arrives.

    We respond with TwiML to start a bidirectional Media Stream.
    """
    form = await request.form()
    call_sid: str = str(form.get("CallSid", "unknown"))
    caller_phone: str = str(form.get("From", "unknown"))
    cfg = get_settings()

    log.info("incoming_call", call_sid=call_sid, caller=caller_phone)

    if not cfg.public_url:
        log.error("public_url_not_set")
        # Still respond with TwiML to avoid Twilio retry loops
    twiml = build_twiml(call_sid, cfg.public_url or "http://localhost:8001")
    return PlainTextResponse(content=twiml, media_type="text/xml")


@router.websocket("/stream/{call_sid}")
async def stream_websocket(websocket: WebSocket, call_sid: str) -> None:
    """Twilio Media Streams WebSocket.

    Twilio sends JSON messages over this socket:
      - connected: stream started
      - start:     stream metadata (caller phone, etc.)
      - media:     audio payload (base64 μ-law, 8 kHz)
      - stop:      caller hung up

    We bridge this to a ``CallPipeline`` by:
      - Converting Twilio μ-law audio → 16 kHz PCM for the pipeline.
      - Converting pipeline TTS output (16 kHz PCM) → 8 kHz μ-law for Twilio.
    """
    await websocket.accept()
    cfg = get_settings()
    caller_phone = "unknown"
    session_id: str | None = None

    # Audio queue: pipeline reads from this
    audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)

    async def receive_loop() -> None:
        """Read Twilio messages and push audio into the queue."""
        nonlocal caller_phone, session_id
        try:
            while True:
                raw = await websocket.receive_text()
                msg = json.loads(raw)
                event = msg.get("event")

                if event == "start":
                    # Extract caller phone from stream params
                    params = msg.get("start", {}).get("customParameters", {})
                    caller_phone = params.get("caller_phone", "unknown")
                    if not caller_phone or caller_phone == "unknown":
                        # Fallback: get from start metadata
                        caller_phone = msg.get("start", {}).get("from", "unknown")

                    log.info("stream_started", call_sid=call_sid, caller=caller_phone)

                    # Create call session in backend
                    async with BackendClient() as client:
                        session_id = await client.start_call(cfg.hospital_id, caller_phone)

                elif event == "media":
                    payload = msg.get("media", {}).get("payload", "")
                    ulaw = base64.b64decode(payload)
                    pcm_8k = ulaw_to_linear(ulaw)
                    pcm_16k = upsample_8k_to_16k(pcm_8k)
                    try:
                        audio_queue.put_nowait(pcm_16k)
                    except asyncio.QueueFull:
                        pass  # drop oldest chunk — tolerable under heavy load

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

    async def send_audio(pcm_16k: bytes) -> None:
        """Send TTS audio back to Twilio (PCM → μ-law → base64 JSON)."""
        ulaw = pcm_16k_to_ulaw_8k(pcm_16k)
        payload = base64.b64encode(ulaw).decode("ascii")
        msg = json.dumps({
            "event": "media",
            "streamSid": call_sid,
            "media": {"payload": payload},
        })
        try:
            await websocket.send_text(msg)
        except Exception:
            pass  # connection may have closed

    # Wait until we have a session_id before starting the pipeline
    receive_task = asyncio.create_task(receive_loop())
    # Give the receive loop time to get the "start" message
    for _ in range(50):  # up to 5 seconds
        await asyncio.sleep(0.1)
        if session_id is not None:
            break

    if session_id is None:
        log.error("no_session_id", call_sid=call_sid)
        receive_task.cancel()
        return

    agent: AgentInterface
    try:
        from agent import MedNexaAgent

        agent = MedNexaAgent(caller_phone, cfg.hospital_id)
        log.info("agent_instantiated", agent="MedNexaAgent", caller=caller_phone)
    except Exception as exc:
        log.warning("failed_to_initialize_mednexa_agent_falling_back", error=str(exc))
        agent = StubAgent(caller_phone, cfg.hospital_id)

    pipeline = CallPipeline(session_id, caller_phone, send_audio, agent=agent)

    pipeline_task = asyncio.create_task(pipeline.run(audio_generator()))

    # Wait for both to complete
    done, pending = await asyncio.wait(
        [receive_task, pipeline_task],
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in pending:
        task.cancel()
