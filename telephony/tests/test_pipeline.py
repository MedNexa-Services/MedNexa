from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from telephony.agent_interface import StubAgent
from telephony.pipeline import CallPipeline


def _make_silence_chunk(frames: int = 5) -> bytes:
    return b"\x00" * (1024 * frames)


def _make_speech_chunk(frames: int = 20) -> bytes:
    return b"\x01\x00" * (512 * frames)


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

        assert len(sent) > 0
        mock_api.append_log.assert_called()
        calls = [call.args for call in mock_api.append_log.call_args_list]
        roles = [c[1] for c in calls]
        assert "ASSISTANT" in roles


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
        events_iter = iter(
            [
                ["speech_start"],
                ["speech", "speech_end"],
                ["silence"],
            ]
        )
        mock_vad.process_chunk.side_effect = list(events_iter)

        chunks_to_send = [
            _make_speech_chunk(3),
            _make_speech_chunk(5),
            _make_silence_chunk(1),
        ]

        sent: list[bytes] = []

        async def send(chunk: bytes) -> None:
            sent.append(chunk)

        async def audio_stream() -> AsyncIterator[bytes]:
            for c in chunks_to_send:
                yield c

        pipeline = CallPipeline("sess-2", "+911234567890", send, agent=StubAgent())
        await pipeline.run(audio_stream())

        mock_stt.transcribe_bytes.assert_called()


class TestChosenLanguage:
    @pytest.mark.asyncio
    async def test_chosen_language_is_used_for_speech_recognition(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        mock_vad.process_chunk.side_effect = [["speech_start"], ["speech_end"], ["silence"]]
        agent = StubAgent()
        agent.fixed_language = None  # type: ignore[attr-defined]  # the real agent has one

        async def send(chunk: bytes) -> None:
            pass

        async def audio_stream() -> AsyncIterator[bytes]:
            for c in (_make_speech_chunk(3), _make_speech_chunk(5), _make_silence_chunk(1)):
                yield c

        pipeline = CallPipeline("sess-hi", "+911234567890", send, agent=agent, language="hi")
        await pipeline.run(audio_stream())

        assert mock_stt.transcribe_bytes.call_args.kwargs["language_hint"] == "hi"
        assert agent.fixed_language == "hi"  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_without_a_choice_the_language_is_detected(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        mock_vad.process_chunk.side_effect = [["speech_start"], ["speech_end"], ["silence"]]

        async def send(chunk: bytes) -> None:
            pass

        async def audio_stream() -> AsyncIterator[bytes]:
            for c in (_make_speech_chunk(3), _make_speech_chunk(5), _make_silence_chunk(1)):
                yield c

        pipeline = CallPipeline("sess-auto", "+911234567890", send, agent=StubAgent())
        await pipeline.run(audio_stream())

        assert mock_stt.transcribe_bytes.call_args.kwargs["language_hint"] is None


class TestBackgroundNoise:
    @staticmethod
    async def _one_utterance(pipeline: CallPipeline) -> None:
        async def audio_stream() -> AsyncIterator[bytes]:
            for c in (_make_speech_chunk(3), _make_speech_chunk(5), _make_silence_chunk(1)):
                yield c

        await pipeline.run(audio_stream())

    @pytest.mark.asyncio
    @pytest.mark.parametrize("text", ["", "you", "Hmm...", "Thanks for watching!"])
    async def test_noise_is_not_answered(
        self,
        text: str,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        from telephony.stt import TranscriptionResult

        mock_stt.transcribe_bytes.return_value = TranscriptionResult(
            text=text, language="en", confidence=0.9, duration_seconds=1.0
        )
        mock_vad.process_chunk.side_effect = [["speech_start"], ["speech_end"], ["silence"]]
        agent = MagicMock(wraps=StubAgent())
        agent.process = AsyncMock()

        async def send(chunk: bytes) -> None:
            pass

        await self._one_utterance(CallPipeline("sess-n", "+911234567890", send, agent=agent))

        agent.process.assert_not_called()
        roles = [c.args[1] for c in mock_api.append_log.call_args_list]
        assert "USER" not in roles

    @pytest.mark.asyncio
    async def test_a_short_low_confidence_sentence_is_still_answered(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        from telephony.stt import TranscriptionResult

        mock_stt.transcribe_bytes.return_value = TranscriptionResult(
            text="just tomorrow.", language="en", confidence=0.26, duration_seconds=1.0
        )
        mock_vad.process_chunk.side_effect = [["speech_start"], ["speech_end"], ["silence"]]
        agent = StubAgent()
        agent.process = AsyncMock(return_value="Sure.")  # type: ignore[method-assign]

        async def send(chunk: bytes) -> None:
            pass

        await self._one_utterance(CallPipeline("sess-n", "+911234567890", send, agent=agent))
        agent.process.assert_awaited_once_with("just tomorrow.", "en")

    @pytest.mark.asyncio
    async def test_audio_is_not_taken_while_the_reply_is_worked_out(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        mock_vad.process_chunk.side_effect = [["speech_start"], ["speech_end"], ["silence"]]
        events: list[dict] = []
        listening_while_thinking: list[bool] = []
        agent = StubAgent()
        pipeline: CallPipeline

        async def on_event(event: dict) -> None:
            events.append(event)

        async def process(text: str, language: str) -> str:
            listening_while_thinking.append(pipeline.listening)
            return "Sure."

        agent.process = process  # type: ignore[method-assign]

        async def send(chunk: bytes) -> None:
            pass

        pipeline = CallPipeline("sess-s", "+911234567890", send, agent=agent, on_event=on_event)
        await self._one_utterance(pipeline)

        states = [e["state"] for e in events if "state" in e]
        assert states == ["thinking", "listening"]
        assert listening_while_thinking == [False]
        lines = [e["transcript"] for e in events if "transcript" in e]
        assert {"role": "user", "text": "I'd like to book an appointment"} in lines
        assert {"role": "assistant", "text": "Sure."} in lines


class TestFailuresDoNotEndTheCall:
    @staticmethod
    async def _call(pipeline: CallPipeline, utterances: int = 1) -> None:
        async def audio() -> AsyncIterator[bytes]:
            for _ in range(utterances):
                yield _make_speech_chunk(3)
                yield _make_speech_chunk(5)
            yield _make_silence_chunk(1)

        await pipeline.run(audio())

    @staticmethod
    def _speech_end_each(vad: MagicMock, utterances: int = 1) -> None:
        vad.process_chunk.side_effect = [
            *([["speech_start"], ["speech_end"]] * utterances),
            ["silence"],
        ]

    @pytest.mark.asyncio
    async def test_a_voice_failure_is_survived_and_the_text_is_offered_to_the_client(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from telephony.tts import TTSUnavailable

        async def broken_stream(text: str, lang: str) -> AsyncIterator[bytes]:
            raise TTSUnavailable("no network")
            yield b""  # pragma: no cover

        tts = MagicMock()
        tts.stream = broken_stream
        monkeypatch.setattr("telephony.pipeline.TTSEngine", lambda: tts)
        self._speech_end_each(mock_vad)
        events: list[dict] = []

        async def on_event(event: dict) -> None:
            events.append(event)

        async def send(chunk: bytes) -> None:
            pass

        pipeline = CallPipeline("s", "+911", send, agent=StubAgent(), on_event=on_event)
        await self._call(pipeline)

        spoken = [e["speak"] for e in events if "speak" in e]
        assert any("Thank you for saying" in text for text in spoken)
        mock_api.end_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_speech_recognition_crash_is_survived(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        mock_stt.transcribe_bytes.side_effect = RuntimeError("whisper crashed")
        self._speech_end_each(mock_vad)

        async def send(chunk: bytes) -> None:
            pass

        await self._call(CallPipeline("s", "+911", send, agent=StubAgent()))
        mock_api.end_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_an_agent_crash_gets_an_apology_and_the_call_goes_on(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        agent = StubAgent()
        agent.process = AsyncMock(side_effect=[RuntimeError("boom"), "Back again."])  # type: ignore[method-assign]
        self._speech_end_each(mock_vad, utterances=2)

        async def send(chunk: bytes) -> None:
            pass

        pipeline = CallPipeline("s", "+911", send, agent=agent)
        await self._call(pipeline, utterances=2)

        said = [c.args[2] for c in mock_api.append_log.call_args_list if c.args[1] == "ASSISTANT"]
        assert any("something went wrong" in text for text in said)
        assert "Back again." in said
        assert agent.process.await_count == 2

    @pytest.mark.asyncio
    async def test_a_slow_agent_gets_a_one_moment_filler(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        agent = StubAgent()

        async def slow(text: str, language: str) -> str:
            await asyncio.sleep(0.3)
            return "Done."

        agent.process = slow  # type: ignore[method-assign]
        self._speak_log: list[str] = []
        spoken: list[str] = []

        async def stream(text: str, lang: str) -> AsyncIterator[bytes]:
            spoken.append(text)
            yield b"\x00" * 10

        mock_tts.stream = stream
        self._speech_end_each(mock_vad)

        async def send(chunk: bytes) -> None:
            pass

        pipeline = CallPipeline("s", "+911", send, agent=agent)
        pipeline._cfg = pipeline._cfg.model_copy(update={"thinking_filler_seconds": 0.05})
        await self._call(pipeline)
        assert "One moment, please." in spoken
        assert spoken.index("One moment, please.") < spoken.index("Done.")

    @pytest.mark.asyncio
    async def test_one_unheard_utterance_is_quiet_but_two_in_a_row_get_a_prompt(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        from telephony.stt import TranscriptionResult

        mock_stt.transcribe_bytes.return_value = TranscriptionResult(
            text="", language="en", confidence=0.0, duration_seconds=1.0
        )
        spoken: list[str] = []

        async def stream(text: str, lang: str) -> AsyncIterator[bytes]:
            spoken.append(text)
            yield b"\x00" * 10

        mock_tts.stream = stream

        async def send(chunk: bytes) -> None:
            pass

        self._speech_end_each(mock_vad)
        await self._call(CallPipeline("s", "+911", send, agent=StubAgent()), utterances=1)
        assert not any("didn't catch" in text for text in spoken)

        spoken.clear()
        self._speech_end_each(mock_vad, utterances=2)
        await self._call(CallPipeline("s", "+911", send, agent=StubAgent()), utterances=2)
        assert sum("didn't catch" in text for text in spoken) == 1


class TestEndOfCall:
    @pytest.mark.asyncio
    async def test_the_last_words_finish_playing_before_the_call_ends(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        import time

        async def send(chunk: bytes) -> None:
            pass

        pipeline = CallPipeline("s", "+911", send, agent=StubAgent())
        pipeline._playback_until = time.monotonic() + 0.3
        started = time.monotonic()
        await pipeline._finish()
        assert time.monotonic() - started >= 0.3
        mock_api.end_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_the_call_is_closed_even_if_cancelled_while_the_last_words_play(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        import time

        async def send(chunk: bytes) -> None:
            pass

        pipeline = CallPipeline("s", "+911", send, agent=StubAgent())
        pipeline._playback_until = time.monotonic() + 30
        task = asyncio.create_task(pipeline._finish())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        mock_api.end_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_hanging_up_during_the_greeting_still_closes_the_call(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def slow_stream(text: str, lang: str) -> AsyncIterator[bytes]:
            await asyncio.sleep(30)
            yield b""

        tts = MagicMock()
        tts.stream = slow_stream
        monkeypatch.setattr("telephony.pipeline.TTSEngine", lambda: tts)

        async def send(chunk: bytes) -> None:
            pass

        async def audio() -> AsyncIterator[bytes]:
            await asyncio.sleep(60)
            yield b""

        task = asyncio.create_task(CallPipeline("s", "+911", send, agent=StubAgent()).run(audio()))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        mock_api.end_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_a_caller_who_hung_up_is_not_waited_for(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        import time

        async def send(chunk: bytes) -> None:
            pass

        pipeline = CallPipeline("s", "+911", send, agent=StubAgent())
        pipeline._playback_until = time.monotonic() + 30

        async def finish_when_cancelled() -> None:
            try:
                await asyncio.sleep(60)
            finally:
                await pipeline._finish()

        task = asyncio.create_task(finish_when_cancelled())
        await asyncio.sleep(0)
        started = time.monotonic()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert time.monotonic() - started < 2
        mock_api.end_call.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_too_short_a_sound_is_not_speech(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("telephony.pipeline.MIN_UTTERANCE_BYTES", 9600)
        mock_vad.process_chunk.side_effect = [["speech_start"], ["speech_end"], ["silence"]]

        async def send(chunk: bytes) -> None:
            pass

        async def audio() -> AsyncIterator[bytes]:
            yield _make_speech_chunk(1)
            yield _make_speech_chunk(1)
            yield _make_silence_chunk(1)

        await CallPipeline("s", "+911", send, agent=StubAgent()).run(audio())
        mock_stt.transcribe_bytes.assert_not_called()


class TestPreRoll:
    @pytest.mark.asyncio
    async def test_audio_just_before_speech_is_kept(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_vad.process_chunk.side_effect = [
            ["silence"],
            ["silence"],
            ["speech_start"],
            ["speech_end"],
            ["silence"],
        ]
        monkeypatch.setattr("telephony.pipeline.normalise_audio", lambda pcm: pcm)
        quiet, before = b"\x00\x00" * 512, b"\x07\x00" * 512
        onset, rest = b"\x01\x00" * 512, b"\x02\x00" * 512

        async def send(chunk: bytes) -> None:
            pass

        async def audio() -> AsyncIterator[bytes]:
            for c in (quiet, before, onset, rest, _make_silence_chunk(1)):
                yield c

        pipeline = CallPipeline("s", "+911", send, agent=StubAgent())
        pipeline._processor.process = lambda chunk: chunk  # type: ignore[method-assign]
        await pipeline.run(audio())
        assert mock_stt.transcribe_bytes.call_args.args[0] == quiet + before + onset + rest


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
        mock_vad.process_chunk.return_value = ["silence"]

        async def endless_silence() -> AsyncIterator[bytes]:
            while True:
                yield _make_silence_chunk(1)

        sent: list[bytes] = []

        async def send(chunk: bytes) -> None:
            sent.append(chunk)

        pipeline = CallPipeline("sess-3", "+91000", send, agent=StubAgent())
        pipeline._cfg = MagicMock()
        pipeline._cfg.silence_timeout_seconds = 0
        pipeline._cfg.call_timeout_seconds = 5
        pipeline._cfg.barge_in_enabled = False
        pipeline._cfg.enable_recordings = False
        pipeline._cfg.hospital_id = "test"

        await asyncio.wait_for(pipeline.run(endless_silence()), timeout=3.0)
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
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("telephony.pipeline.normalise_audio", lambda pcm: pcm)
        chunks = [b"\x01\x00" * 100, b"\x02\x00" * 100, b"\x03\x00" * 1100, b"\x04\x00" * 100]
        script = [
            (["speech_start"], True),
            ([], True),
            (["speech", "speech"], True),
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
        pipeline._processor = MagicMock(process=lambda c: c)
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

        async def one_second_of_speech(text: str, lang: str) -> AsyncIterator[bytes]:
            for _ in range(10):
                yield b"\x00" * 3200

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

        clear.assert_awaited_once()

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
            await asyncio.sleep(0.05)
            yield b"\x01\x00" * 320

        async def send(chunk: bytes) -> None:
            pass

        pipeline = CallPipeline(
            "sess-quiet", "+911234567890", send, clear_audio=clear, agent=StubAgent()
        )
        await pipeline.run(caller_speaks())
        clear.assert_not_awaited()


class TestCallEnd:
    @pytest.mark.asyncio
    async def test_end_call_reports_the_agents_outcome(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        agent = StubAgent()
        agent.call_outcome = "BOOKED"  # type: ignore[attr-defined]
        agent.escalated = True  # type: ignore[attr-defined]

        async def no_audio() -> AsyncIterator[bytes]:
            return
            yield  # type: ignore[misc]

        async def send(chunk: bytes) -> None:
            pass

        await CallPipeline("sess-end", "+911234567890", send, agent=agent).run(no_audio())
        kwargs = mock_api.end_call.await_args.kwargs
        assert kwargs["outcome"] == "BOOKED"
        assert kwargs["escalated_to_human"] is True

    @pytest.mark.asyncio
    async def test_agents_without_an_outcome_end_as_other(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        async def no_audio() -> AsyncIterator[bytes]:
            return
            yield  # type: ignore[misc]

        async def send(chunk: bytes) -> None:
            pass

        await CallPipeline("sess-end2", "+911234567890", send, agent=StubAgent()).run(no_audio())
        assert mock_api.end_call.await_args.kwargs["outcome"] == "OTHER"


class EscalatingAgent(StubAgent):
    escalated = False

    async def process(self, text: str, language: str = "en") -> str:
        self.escalated = True
        return "Let me connect you to our staff. Please stay on the line."


class TestHandOver:
    @staticmethod
    def two_utterances(mock_vad: MagicMock) -> AsyncIterator[bytes]:
        mock_vad.process_chunk.side_effect = [["speech", "speech_end"]] * 2

        async def stream() -> AsyncIterator[bytes]:
            for _ in range(2):
                yield _make_speech_chunk(3)

        return stream()

    @staticmethod
    async def send(chunk: bytes) -> None:
        pass

    @pytest.mark.asyncio
    async def test_escalated_call_is_transferred_and_the_ai_stops(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
    ) -> None:
        transfer = AsyncMock(return_value=True)
        pipeline = CallPipeline(
            "sess-t", "+911234567890", self.send, transfer=transfer, agent=EscalatingAgent()
        )
        await pipeline.run(self.two_utterances(mock_vad))

        transfer.assert_awaited_once()
        assert mock_stt.transcribe_bytes.call_count == 1
        assert mock_api.end_call.await_args.kwargs["escalated_to_human"] is True

    @pytest.mark.parametrize("transfer", [None, AsyncMock(return_value=False)])
    @pytest.mark.asyncio
    async def test_caller_is_told_to_call_reception_when_transfer_is_impossible(
        self,
        mock_vad: MagicMock,
        mock_stt: MagicMock,
        mock_tts: MagicMock,
        mock_api: MagicMock,
        mock_recorder: MagicMock,
        transfer: AsyncMock | None,
    ) -> None:
        pipeline = CallPipeline(
            "sess-n", "+911234567890", self.send, transfer=transfer, agent=EscalatingAgent()
        )
        await pipeline.run(self.two_utterances(mock_vad))

        said = [c.args[2] for c in mock_api.append_log.await_args_list if c.args[1] == "ASSISTANT"]
        assert "call the hospital reception directly" in said[-1]
        assert mock_stt.transcribe_bytes.call_count == 1


@pytest.mark.asyncio
async def test_backend_client_sends_backend_role_values() -> None:
    from telephony.api_client import BackendClient

    client = BackendClient(base_url="http://test")
    client._post = AsyncMock()  # type: ignore[method-assign]
    await client.append_log("s1", "assistant", "hello")
    assert client._post.await_args.args[1]["role"] == "ASSISTANT"
    await client.aclose()


@pytest.mark.parametrize(
    "reply, ends_call",
    [
        ("Thank you for calling, goodbye!", True),
        ("Okay, bye.", True),
        ("धन्यवाद, नमस्ते!", True),
        ("धन्यवाद, आपकी अपॉइंटमेंट बुक हो गई है। और कुछ?", False),
        ("Take care. Your token number is 3. Anything else?", False),
        ("Thank you for calling MedNexa. How can I help?", False),
        ("Dr. Sharma is nearby in room 4.", False),
    ],
)
def test_farewell_detection(reply: str, ends_call: bool) -> None:
    assert CallPipeline._is_farewell(reply) is ends_call
