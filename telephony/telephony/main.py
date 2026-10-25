"""FastAPI application for the telephony server.

Starts a small HTTP + WebSocket server that:
  - Receives Twilio webhooks (POST /twilio/voice)
  - Handles Twilio Media Streams (WS /twilio/stream/{call_sid})
  - Exposes a health check (GET /health)
  - Exposes a WebSocket bridge for local testing (WS /ws/call)

Run with::

    uvicorn telephony.main:app --host 0.0.0.0 --port 8001 --reload
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from telephony.api_client import BackendClient
from telephony.config import get_settings
from telephony.logging_setup import configure_logging, get_logger
from telephony.stt import FasterWhisperSTT
from telephony.tts import TTSEngine
from telephony.twilio_handler import router as twilio_router
from telephony.vad import SileroVAD

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # type: ignore[type-arg]
    """Pre-load heavy models at startup so the first call isn't slow."""
    configure_logging()
    cfg = get_settings()
    log.info("telephony_starting", host=cfg.server_host, port=cfg.server_port)

    # Pre-load VAD model (shared class attribute — loaded once)
    log.info("preloading_vad")
    SileroVAD._load_model()

    # Pre-load Whisper model
    log.info("preloading_whisper")
    FasterWhisperSTT()._load()

    # Health-check backend
    async with BackendClient() as client:
        healthy = await client.health_check()
    if not healthy:
        log.warning("backend_unreachable", url=cfg.backend_url)
    else:
        log.info("backend_connected", url=cfg.backend_url)

    log.info("telephony_ready")
    yield

    log.info("telephony_shutting_down")


def create_app() -> FastAPI:
    cfg = get_settings()
    app = FastAPI(
        title="MedNexa Telephony",
        description="Voice/Telephony pipeline — Part 3",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Twilio webhook + media stream
    app.include_router(twilio_router)

    # ── Health check ──────────────────────────────────────────────────────────
    @app.get("/health", tags=["system"])
    async def health() -> JSONResponse:
        async with BackendClient() as client:
            backend_ok = await client.health_check()
        return JSONResponse({
            "status": "ok",
            "backend_connected": backend_ok,
        })

    # ── Local WebSocket test bridge ───────────────────────────────────────────
    # Connect with a raw WebSocket client and stream raw 16 kHz PCM audio.
    # Useful for integration tests without Twilio.
    @app.websocket("/ws/call")
    async def ws_call(websocket: WebSocket) -> None:
        """Raw PCM WebSocket bridge for local integration testing.

        Protocol:
          Client → Server: raw int16 LE PCM bytes (16 kHz mono)
          Server → Client: raw int16 LE PCM bytes (TTS responses)
          Session lifecycle: auto-start on connect, auto-end on disconnect.
        """
        from telephony.pipeline import CallPipeline

        await websocket.accept()
        cfg = get_settings()
        caller_phone = websocket.query_params.get("phone", "test_caller")

        async with BackendClient() as client:
            session_id = await client.start_call(cfg.hospital_id, caller_phone)

        log.info("ws_call_connected", session_id=session_id, caller=caller_phone)

        audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=200)

        async def receive_loop() -> None:
            try:
                while True:
                    chunk = await websocket.receive_bytes()
                    if not chunk:
                        break
                    audio_queue.put_nowait(chunk)
            except WebSocketDisconnect:
                pass
            finally:
                await audio_queue.put(b"")

        async def audio_gen() -> AsyncIterator[bytes]:
            while True:
                chunk = await audio_queue.get()
                if not chunk:
                    return
                yield chunk

        async def send_audio(pcm: bytes) -> None:
            try:
                await websocket.send_bytes(pcm)
            except Exception:
                pass

        recv_task = asyncio.create_task(receive_loop())
        pipeline = CallPipeline(session_id, caller_phone, send_audio)
        pipe_task = asyncio.create_task(pipeline.run(audio_gen()))

        done, pending = await asyncio.wait(
            [recv_task, pipe_task], return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()

        log.info("ws_call_ended", session_id=session_id)

    return app


app = create_app()
