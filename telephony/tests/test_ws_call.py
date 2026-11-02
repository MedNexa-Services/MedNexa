from __future__ import annotations

import asyncio
import itertools
import json
import socket
from collections.abc import AsyncIterator, Iterator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import uvicorn
import websockets

from telephony import capacity
from telephony.agent_interface import StubAgent
from telephony.main import create_app

FRAME = b"\x01\x00" * 512


@pytest.fixture()
async def server(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[str]:
    import telephony.config as cfg_module

    monkeypatch.setattr(cfg_module._settings, "use_stub_agent", True)  # type: ignore[attr-defined]
    backend = MagicMock()
    backend.start_call = AsyncMock(return_value="session-1")
    backend.__aenter__ = AsyncMock(return_value=backend)
    backend.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("telephony.main.BackendClient", lambda: backend)
    capacity.calls._active = 0

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    config = uvicorn.Config(
        create_app(), host="127.0.0.1", port=port, lifespan="off", log_level="error"
    )
    instance = uvicorn.Server(config)
    task = asyncio.create_task(instance.serve())
    while not instance.started:  # noqa: ASYNC110 - uvicorn offers no event for this
        await asyncio.sleep(0.01)
    yield f"ws://127.0.0.1:{port}/ws/call"
    instance.should_exit = True
    await task


def one_utterance_then_silence(vad: MagicMock) -> None:
    events: Iterator[list[str]] = itertools.chain(
        [["speech_start"], ["speech_end"]], itertools.repeat(["silence"])
    )
    vad.process_chunk.side_effect = lambda chunk: next(events)


async def messages_until_closed(ws: websockets.ClientConnection, pace: float = 0.005) -> list:
    got: list = []

    async def send() -> None:
        while True:
            await ws.send(FRAME)
            await asyncio.sleep(pace)

    sender = asyncio.create_task(send())
    try:
        async for message in ws:
            got.append(json.loads(message) if isinstance(message, str) else message)
    except websockets.ConnectionClosed:
        pass
    finally:
        sender.cancel()
    return got


@pytest.mark.asyncio
async def test_the_server_ends_the_call_after_the_agent_says_goodbye(
    server: str,
    mock_vad: MagicMock,
    mock_stt: MagicMock,
    mock_tts: MagicMock,
    mock_api: MagicMock,
    mock_recorder: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(StubAgent, "process", AsyncMock(return_value="Thank you. Goodbye."))
    one_utterance_then_silence(mock_vad)

    async with websockets.connect(server + "?phone=%2B911234567890&lang=en") as ws:
        got = await asyncio.wait_for(messages_until_closed(ws), timeout=15)

    assert {"ended": True} in got
    lines = [m["transcript"] for m in got if isinstance(m, dict) and "transcript" in m]
    assert {"role": "assistant", "text": "Thank you. Goodbye."} in lines
    assert any(isinstance(m, bytes) for m in got)
    mock_api.end_call.assert_awaited_once()


@pytest.mark.asyncio
async def test_the_call_session_is_ended_when_the_caller_hangs_up(
    server: str,
    mock_vad: MagicMock,
    mock_stt: MagicMock,
    mock_tts: MagicMock,
    mock_api: MagicMock,
    mock_recorder: MagicMock,
) -> None:
    async with websockets.connect(server + "?lang=en") as ws:
        await ws.recv()
        for _ in range(5):
            await ws.send(FRAME)
    for _ in range(100):
        if mock_api.end_call.await_count and capacity.calls.active == 0:
            break
        await asyncio.sleep(0.05)
    mock_api.end_call.assert_awaited_once()
    assert capacity.calls.active == 0


@pytest.mark.asyncio
async def test_a_busy_line_turns_the_caller_away_politely(
    server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(capacity.calls, "_active", 10)
    async with websockets.connect(server) as ws:
        message = json.loads(await ws.recv())
        assert "busy" in message["error"]
        with pytest.raises(websockets.ConnectionClosed):
            await ws.recv()


@pytest.mark.asyncio
async def test_an_unreachable_backend_is_reported_not_crashed(
    server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = MagicMock()
    broken.__aenter__ = AsyncMock(side_effect=OSError("backend down"))
    broken.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("telephony.main.BackendClient", lambda: broken)
    async with websockets.connect(server) as ws:
        message = json.loads(await ws.recv())
        assert "can't be reached" in message["error"]
    assert capacity.calls.active == 0


@pytest.mark.asyncio
async def test_the_test_page_is_served_without_caching(server: str) -> None:
    page = server.replace("ws://", "http://").replace("/ws/call", "/call")
    async with httpx.AsyncClient() as client:
        response = await client.get(page)
    assert response.status_code == 200
    assert "Test call" in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_the_test_line_can_be_turned_off(
    server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import telephony.config as cfg_module

    monkeypatch.setattr(cfg_module._settings, "web_call_enabled", False)  # type: ignore[attr-defined]
    page = server.replace("ws://", "http://").replace("/ws/call", "/call")
    async with httpx.AsyncClient() as client:
        assert (await client.get(page)).status_code == 404
    with pytest.raises(websockets.exceptions.InvalidStatus):
        async with websockets.connect(server):
            pass
