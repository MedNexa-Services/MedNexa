from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from telephony import capacity
from telephony.api_client import BackendClient
from telephony.config import get_settings
from telephony.logging_setup import configure_logging, get_logger
from telephony.pipeline import fixed_phrases
from telephony.stt import FasterWhisperSTT
from telephony.tts import TTSEngine
from telephony.twilio_handler import router as twilio_router
from telephony.vad import SileroVAD

configure_logging()
log = get_logger("main")

CALL_PAGE = Path(__file__).with_name("call.html")


async def _prewarm_voice(hospital_id: str) -> None:
    phrases = fixed_phrases()
    if hospital_id:
        from telephony.agent_interface import create_agent

        for language, voice in (("en", "en"), (None, "en"), ("hi", "hi")):
            try:
                agent = create_agent("", hospital_id)
                if hasattr(agent, "fixed_language"):
                    agent.fixed_language = language
                phrases[voice].insert(0, await agent.get_greeting())
            except Exception:
                log.warning("greeting_prewarm_failed", language=language)
    await TTSEngine().prewarm(phrases)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:  # type: ignore[type-arg]
    cfg = get_settings()
    log.info("telephony_starting", host=cfg.server_host, port=cfg.server_port)

    log.info("preloading_models")
    SileroVAD._load_model()
    await asyncio.to_thread(FasterWhisperSTT().warm_up)
    prewarm = asyncio.create_task(_prewarm_voice(cfg.hospital_id))

    if not cfg.hospital_id:
        log.error(
            "hospital_id_not_set",
            hint="set MEDNEXA_TEL_HOSPITAL_ID to the hospital's UUID; calls cannot be logged",
        )
    if not cfg.backend_api_key:
        log.warning(
            "backend_api_key_not_set",
            hint="set MEDNEXA_TEL_BACKEND_API_KEY (the backend's MEDNEXA_SERVICE_API_KEY); "
            "an authenticated backend rejects call logs without it",
        )
    if cfg.twilio_auth_token and not cfg.transfer_phone_number:
        log.warning(
            "transfer_phone_number_not_set",
            hint="set MEDNEXA_TEL_TRANSFER_PHONE_NUMBER so callers who ask for a person "
            "are connected to staff (otherwise they are asked to call reception)",
        )

    async with BackendClient() as client:
        healthy = await client.health_check()
    if not healthy:
        log.warning("backend_unreachable", url=cfg.backend_url)
    else:
        log.info("backend_connected", url=cfg.backend_url)

    log.info("telephony_ready")
    yield

    log.info("telephony_shutting_down")
    prewarm.cancel()


def create_app() -> FastAPI:
    app = FastAPI(
        title="MedNexa Telephony",
        description="Phone calls answered by the MedNexa AI receptionist",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(twilio_router)

    @app.get("/health", tags=["system"])
    async def health() -> JSONResponse:
        async with BackendClient() as client:
            backend_ok = await client.health_check()
        hospital_configured = bool(get_settings().hospital_id)
        return JSONResponse(
            {
                "status": "ok" if backend_ok and hospital_configured else "degraded",
                "backend_connected": backend_ok,
                "hospital_configured": hospital_configured,
            }
        )

    @app.get("/call", response_class=HTMLResponse)
    async def call_page() -> HTMLResponse:
        if not get_settings().web_call_enabled:
            raise HTTPException(status_code=404)
        return HTMLResponse(
            CALL_PAGE.read_text(encoding="utf-8"), headers={"Cache-Control": "no-store"}
        )

    @app.websocket("/ws/call")
    async def ws_call(websocket: WebSocket) -> None:
        if not get_settings().web_call_enabled:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        caller_phone = websocket.query_params.get("phone", "anonymous")
        language = websocket.query_params.get("lang")
        language = language if language in ("en", "hi") else None

        if not capacity.calls.try_acquire():
            log.warning("ws_call_refused_busy", active=capacity.calls.active)
            await _refuse(websocket, "All lines are busy. Please try again in a moment.")
            return
        try:
            await _run_ws_call(websocket, caller_phone, language)
        finally:
            capacity.calls.release()

    return app


async def _refuse(websocket: WebSocket, reason: str) -> None:
    with contextlib.suppress(Exception):
        await websocket.send_text(json.dumps({"error": reason}))
        await websocket.close(code=1013)


async def _run_ws_call(websocket: WebSocket, caller_phone: str, language: str | None) -> None:
    from telephony.pipeline import CallPipeline

    try:
        async with BackendClient() as client:
            session_id = await client.start_call(get_settings().hospital_id, caller_phone)
    except Exception:
        log.exception("ws_call_start_failed")
        await _refuse(websocket, "The hospital system can't be reached right now. Try again.")
        return
    log.info("ws_call_connected", session_id=session_id, caller=caller_phone)

    audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=2000)

    async def receive_loop() -> None:
        try:
            while True:
                chunk = await websocket.receive_bytes()
                if not chunk:
                    break
                if not pipeline.listening:
                    continue
                if audio_queue.full():
                    audio_queue.get_nowait()
                audio_queue.put_nowait(chunk)
        except WebSocketDisconnect:
            pass
        except Exception:
            log.exception("ws_receive_error")
        finally:
            audio_queue.put_nowait(b"")

    async def audio_gen() -> AsyncIterator[bytes]:
        while True:
            chunk = await audio_queue.get()
            if not chunk:
                return
            yield chunk

    async def send_audio(pcm: bytes) -> None:
        with contextlib.suppress(Exception):
            await websocket.send_bytes(pcm)

    async def send_event(event: dict[str, Any]) -> None:
        await websocket.send_text(json.dumps(event))

    pipeline = CallPipeline(
        session_id, caller_phone, send_audio, language=language, on_event=send_event
    )
    recv_task = asyncio.create_task(receive_loop())
    pipe_task = asyncio.create_task(pipeline.run(audio_gen()))

    done, pending = await asyncio.wait([recv_task, pipe_task], return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        if not task.cancelled() and task.exception() is not None:
            log.error("ws_call_task_failed", error=repr(task.exception()))
    if pipe_task in done:
        with contextlib.suppress(Exception):
            await send_event({"ended": True})
            await websocket.close()
    log.info("ws_call_ended", session_id=session_id)


app = create_app()
