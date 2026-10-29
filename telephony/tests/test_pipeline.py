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
        events_iter = iter(
            [
                ["speech_start"],  # first chunk
                ["speech", "speech_end"],  # second chunk — triggers STT
                ["silence"],
            ]
        )
        mock_vad.process_chunk.side_effect = list(events_iter)

        chunks_to_send = [
            _make_speech_chunk(3),  # speech_start
            _make_speech_chunk(5),  # speech_end
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


class TestUtteranceBuffering:
    @pytest.mark.asyncio
    async def test_utterance_keeps_every_chunk_exactly_once(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        """Chunks without a VAD event mid-speech are kept; multi-frame chunks aren't doubled."""
        chunks = [b"\x01\x00" * 100, b"\x02\x00" * 100, b"\x03\x00" * 1100, b"\x04\x00" * 100]
        script = [
            (["speech_start"], True),
            ([], True),  # shorter than a VAD frame: no event, but still mid-utterance
            (["speech", "speech"], True),  # two frames in one chunk
            (["speech_end"], False),
        ]

        def process_chunk(chunk: bytes) -> list[str]:
            events, in_speech = script.pop(0)
            mock_vad.in_speech = in_speech
            return events

        mock_vad.process_chunk.side_effect = process_chunk

        async def audio() -> AsyncIterator[bytes]:
            for c in chunks:
                yield c

        async def send(chunk: bytes) -> None:
            pass

        pipeline = CallPipeline("sess-buf", "+911234567890", send, agent=StubAgent())
        pipeline._processor = MagicMock(process=lambda c: c)  # pass audio through unchanged
        await pipeline.run(audio())

        transcribed = mock_stt.transcribe_bytes.call_args.args[0]
        assert transcribed == b"".join(chunks)


class TestBargeIn:
    @pytest.mark.asyncio
    async def test_caller_speech_during_playback_clears_queued_audio(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Audio is sent faster than real time; the caller is still hearing the
        greeting when they start talking, so the queued audio must be cleared."""

        async def one_second_of_speech(text: str, lang: str) -> AsyncIterator[bytes]:
            for _ in range(10):
                yield b"\x00" * 3200  # 10 x 100 ms

        tts = MagicMock()
        tts.stream = one_second_of_speech
        monkeypatch.setattr("telephony.pipeline.TTSEngine", lambda: tts)

        events = [["speech_start"], ["speech"]]

        def process_chunk(chunk: bytes) -> list[str]:
            mock_vad.in_speech = True
            return events.pop(0) if events else ["speech"]

        mock_vad.process_chunk.side_effect = process_chunk

        async def caller_interrupts() -> AsyncIterator[bytes]:
            yield b"\x01\x00" * 320
            yield b"\x01\x00" * 320

        clear = AsyncMock()

        async def send(chunk: bytes) -> None:
            pass

        pipeline = CallPipeline(
            "sess-barge", "+911234567890", send, clear_audio=clear, agent=StubAgent()
        )
        await pipeline.run(caller_interrupts())

        clear.assert_awaited_once()  # once, not again for the second speech chunk

    @pytest.mark.asyncio
    async def test_no_clear_when_nothing_is_playing(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        mock_vad.process_chunk.side_effect = lambda chunk: ["speech_start"]
        clear = AsyncMock()

        async def caller_speaks() -> AsyncIterator[bytes]:
            await asyncio.sleep(0.05)  # the tiny greeting (100 bytes) has finished playing
            yield b"\x01\x00" * 320

        async def send(chunk: bytes) -> None:
            pass

        pipeline = CallPipeline(
            "sess-quiet", "+911234567890", send, clear_audio=clear, agent=StubAgent()
        )
        await pipeline.run(caller_speaks())
        clear.assert_not_awaited()
