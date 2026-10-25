"""Integration tests for CallPipeline.

These tests run the pipeline end-to-end using:
  - Mocked Silero VAD (no torch model loaded)
  - Mocked Faster-Whisper STT
  - Mocked TTS engine
  - StubAgent
  - Mocked BackendClient

No external services or GPU required.
"""

from __future__ import annotations

import asyncio
import struct
from collections import deque
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telephony.agent_interface import StubAgent
from telephony.pipeline import CallPipeline


def _make_silence_chunk(frames: int = 5) -> bytes:
    """512 samples × 2 bytes × frames of silence."""
    return b"\x00" * (1024 * frames)


def _make_speech_chunk(frames: int = 20) -> bytes:
    """Non-zero audio to simulate speech frames."""
    return b"\x01\x00" * (512 * frames)


@pytest.fixture()
def mock_vad(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace SileroVAD with a mock that returns configurable events."""
    vad = MagicMock()
    vad.in_speech = False
    vad.process_chunk.return_value = ["silence"]
    vad.reset.return_value = None
    monkeypatch.setattr("telephony.pipeline.SileroVAD", lambda: vad)
    return vad


@pytest.fixture()
def mock_stt(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace FasterWhisperSTT with a mock."""
    from telephony.stt import TranscriptionResult

    stt = MagicMock()
    stt.transcribe_bytes.return_value = TranscriptionResult(
        text="I'd like to book an appointment",
        language="en",
        confidence=0.9,
        duration_seconds=2.0,
    )
    monkeypatch.setattr("telephony.pipeline.FasterWhisperSTT", lambda: stt)
    return stt


@pytest.fixture()
def mock_tts(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace TTSEngine with a mock that streams one empty chunk."""

    async def fake_stream(text: str, lang: str) -> AsyncIterator[bytes]:
        yield b"\x00" * 100

    tts = MagicMock()
    tts.stream = fake_stream
    monkeypatch.setattr("telephony.pipeline.TTSEngine", lambda: tts)
    return tts


@pytest.fixture()
def mock_api(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace BackendClient with an async mock."""
    client = AsyncMock()
    client.append_log = AsyncMock()
    client.end_call = AsyncMock()
    client.aclose = AsyncMock()
    monkeypatch.setattr("telephony.pipeline.BackendClient", lambda: client)
    return client


@pytest.fixture()
def mock_recorder(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Replace CallRecorder with a no-op mock."""
    recorder = MagicMock()
    recorder.enabled = False
    recorder.__enter__ = MagicMock(return_value=recorder)
    recorder.__exit__ = MagicMock(return_value=None)
    recorder.write = MagicMock()
    monkeypatch.setattr("telephony.pipeline.CallRecorder", lambda sid: recorder)
    return recorder


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestPipelineGreeting:
    @pytest.mark.asyncio
    async def test_greeting_is_spoken_and_logged(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        sent: list[bytes] = []

        async def send(chunk: bytes) -> None:
            sent.append(chunk)

        async def empty_stream() -> AsyncIterator[bytes]:
            return
            yield  # type: ignore[misc]

        pipeline = CallPipeline("sess-1", "+911234567890", send, agent=StubAgent())
        await pipeline.run(empty_stream())

        # Greeting should have been spoken (sent at least one chunk)
        assert len(sent) > 0
        # Greeting should have been logged
        mock_api.append_log.assert_called()
        calls = [call.args for call in mock_api.append_log.call_args_list]
        roles = [c[1] for c in calls]
        assert "assistant" in roles


class TestPipelineUtterance:
    @pytest.mark.asyncio
    async def test_speech_end_triggers_stt_and_response(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        """When VAD signals speech_end, STT and agent should be called."""
        # Produce speech_start → speech_end → silence from the mock VAD
        events_iter = iter([
            ["speech_start"],  # first chunk
            ["speech", "speech_end"],  # second chunk — triggers STT
            ["silence"],
        ])
        mock_vad.process_chunk.side_effect = list(events_iter)

        chunks_to_send = [
            _make_speech_chunk(3),   # speech_start
            _make_speech_chunk(5),   # speech_end
            _make_silence_chunk(1),  # silence (stops the loop naturally)
        ]

        sent: list[bytes] = []

        async def send(chunk: bytes) -> None:
            sent.append(chunk)

        async def audio_stream() -> AsyncIterator[bytes]:
            for c in chunks_to_send:
                yield c

        pipeline = CallPipeline("sess-2", "+911234567890", send, agent=StubAgent())
        await pipeline.run(audio_stream())

        # STT should have been called
        mock_stt.transcribe_bytes.assert_called()


class TestPipelineTimeout:
    @pytest.mark.asyncio
    async def test_silence_timeout_ends_call(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        """A call with no speech should time out."""
        mock_vad.process_chunk.return_value = ["silence"]

        async def endless_silence() -> AsyncIterator[bytes]:
            while True:
                yield _make_silence_chunk(1)

        sent: list[bytes] = []

        async def send(chunk: bytes) -> None:
            sent.append(chunk)

        # Use very short timeout for the test
        pipeline = CallPipeline("sess-3", "+91000", send, agent=StubAgent())
        pipeline._cfg = MagicMock()
        pipeline._cfg.silence_timeout_seconds = 0  # immediate
        pipeline._cfg.call_timeout_seconds = 5
        pipeline._cfg.barge_in_enabled = False
        pipeline._cfg.enable_recordings = False
        pipeline._cfg.hospital_id = "test"

        await asyncio.wait_for(pipeline.run(endless_silence()), timeout=3.0)
        # end_call should have been called
        mock_api.end_call.assert_called_once()
