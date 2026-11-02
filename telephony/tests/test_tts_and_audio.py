from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from telephony.tts import (
    CHUNK_BYTES,
    SAMPLE_RATE,
    PiperTTS,
    TTSEngine,
    TTSUnavailable,
    _decode_mp3,
    split_sentences,
    trim_silence,
)


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    TTSEngine._cache.clear()
    monkeypatch.setattr("telephony.tts._retry_pause", AsyncMock())


def make_engine(*, piper: object | None = None, edge: object | None = None) -> TTSEngine:
    engine = TTSEngine.__new__(TTSEngine)
    engine._prefer_piper = piper is not None
    engine._piper_ok = None if piper is not None else False
    engine._piper = piper or MagicMock()
    engine._edge = edge or MagicMock()
    engine._retries = 2
    engine._timeout = 5.0
    engine._cache_size = 4
    return engine


def edge_returning(*results: object) -> AsyncMock:
    edge = AsyncMock()
    edge.synthesize = AsyncMock(side_effect=list(results))
    return edge


class TestTTSEngine:
    @pytest.mark.asyncio
    async def test_empty_text_returns_empty(self) -> None:
        assert await make_engine().speak("", "en") == b""

    @pytest.mark.asyncio
    async def test_text_without_words_is_not_synthesised(self) -> None:
        edge = edge_returning()
        assert await make_engine(edge=edge).speak(" ... ", "en") == b""
        edge.synthesize.assert_not_called()

    @pytest.mark.asyncio
    async def test_falls_back_to_edge_when_piper_unavailable(self) -> None:
        piper = MagicMock()
        piper._is_available.return_value = False
        edge = edge_returning(b"\x00" * 100)
        engine = make_engine(piper=piper, edge=edge)

        assert await engine.speak("Hello", "en") == b"\x00" * 100
        edge.synthesize.assert_called_once_with("Hello", "en")

    @pytest.mark.asyncio
    async def test_uses_piper_when_available(self) -> None:
        piper = MagicMock()
        piper._is_available.return_value = True
        piper.synthesize = AsyncMock(return_value=b"\x01" * 200)
        engine = make_engine(piper=piper)

        assert await engine.speak("Namaste", "hi") == b"\x01" * 200
        piper.synthesize.assert_called_once_with("Namaste", "hi")

    @pytest.mark.asyncio
    async def test_piper_failure_falls_back_to_edge(self) -> None:
        piper = MagicMock()
        piper._is_available.return_value = True
        piper.synthesize = AsyncMock(side_effect=RuntimeError("piper crashed"))
        engine = make_engine(piper=piper, edge=edge_returning(b"\x02" * 50))

        assert await engine.speak("Test", "en") == b"\x02" * 50
        assert engine._piper_ok is False

    @pytest.mark.asyncio
    async def test_a_failed_attempt_is_retried(self) -> None:
        edge = edge_returning(OSError("name resolution"), OSError("name resolution"), b"\x03" * 10)
        assert await make_engine(edge=edge).speak("Hello", "en") == b"\x03" * 10
        assert edge.synthesize.call_count == 3

    @pytest.mark.asyncio
    async def test_it_gives_up_after_the_retries(self) -> None:
        edge = edge_returning(*[OSError("down")] * 5)
        with pytest.raises(TTSUnavailable):
            await make_engine(edge=edge).speak("Hello", "en")
        assert edge.synthesize.call_count == 3

    @pytest.mark.asyncio
    async def test_a_hanging_service_times_out(self) -> None:
        async def hang(text: str, language: str) -> bytes:
            await asyncio.sleep(60)
            return b""

        engine = make_engine(edge=MagicMock(synthesize=hang))
        engine._timeout = 0.05
        engine._retries = 0
        with pytest.raises(TTSUnavailable):
            await engine.speak("Hello", "en")

    @pytest.mark.asyncio
    async def test_a_sentence_is_made_once_and_remembered(self) -> None:
        edge = edge_returning(b"\x04" * 20)
        engine = make_engine(edge=edge)
        assert await engine.speak("Hello", "en") == b"\x04" * 20
        assert await engine.speak("Hello", "en") == b"\x04" * 20
        assert edge.synthesize.call_count == 1

    @pytest.mark.asyncio
    async def test_the_cache_is_bounded(self) -> None:
        edge = AsyncMock()
        edge.synthesize = AsyncMock(return_value=b"\x05\x00")
        engine = make_engine(edge=edge)
        for word in ["one", "two", "three", "four", "five", "six"]:
            await engine.speak(word, "en")
        assert len(TTSEngine._cache) == 4

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self) -> None:
        engine = make_engine(edge=edge_returning(b"\x00" * (CHUNK_BYTES * 2)))
        chunks = [c async for c in engine.stream("Hello world", "en")]
        assert len(chunks) == 2
        assert all(len(c) == CHUNK_BYTES for c in chunks)

    @pytest.mark.asyncio
    async def test_a_long_reply_is_made_sentence_by_sentence_in_order(self) -> None:
        reply = (
            "Your appointment is booked for Tuesday at nine in the morning. "
            "Your token number is three, so please arrive about fifteen minutes early."
        )
        edge = AsyncMock()
        edge.synthesize = AsyncMock(side_effect=lambda text, lang: text.encode()[:1] * 8)
        engine = make_engine(edge=edge)
        audio = b"".join([c async for c in engine.stream(reply, "en")])
        assert edge.synthesize.call_count == 2
        assert audio == b"Y" * 8 + b"Y" * 8

    @pytest.mark.asyncio
    async def test_a_failed_later_sentence_stops_the_stream_after_the_earlier_audio(self) -> None:
        edge = AsyncMock()

        async def synth(text: str, lang: str) -> bytes:
            if text.startswith("Please"):
                raise OSError("down")
            return b"\x01" * 4

        edge.synthesize = synth
        engine = make_engine(edge=edge)
        got: list[bytes] = []
        with pytest.raises(TTSUnavailable):
            async for chunk in engine.stream(
                "Your appointment is booked for Tuesday at nine. "
                "Please arrive about fifteen minutes early.",
                "en",
            ):
                got.append(chunk)
        assert got == [b"\x01" * 4]

    @pytest.mark.asyncio
    async def test_prewarm_makes_fixed_phrases_and_survives_failures(self) -> None:
        edge = edge_returning(b"\x01\x00", OSError("x"), OSError("x"), OSError("x"), b"\x02\x00")
        done = await make_engine(edge=edge).prewarm(
            {"en": ["One moment, please."], "hi": ["नमस्ते"], "x": ["Bye"]}
        )
        assert done == 2


class TestDecodeMp3:
    def test_ffmpeg_output_is_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, object] = {}

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            seen["cmd"], seen["input"] = cmd, kwargs["input"]
            return MagicMock(returncode=0, stdout=b"\x01\x02" * 8, stderr=b"")

        monkeypatch.setattr("telephony.tts.subprocess.run", fake_run)
        assert _decode_mp3(b"mp3-bytes") == b"\x01\x02" * 8
        assert seen["input"] == b"mp3-bytes"
        assert "-ar" in seen["cmd"] and "16000" in seen["cmd"]  # type: ignore[operator]

    def test_an_ffmpeg_failure_is_an_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "telephony.tts.subprocess.run",
            lambda *a, **k: MagicMock(returncode=1, stdout=b"", stderr=b"bad data"),
        )
        with pytest.raises(RuntimeError, match="bad data"):
            _decode_mp3(b"x")


def tone(seconds: float, amplitude: int = 8000) -> bytes:
    return np.full(int(SAMPLE_RATE * seconds), amplitude, dtype=np.int16).tobytes()


def silence(seconds: float) -> bytes:
    return bytes(int(SAMPLE_RATE * seconds) * 2)


class TestTrimSilence:
    def test_the_silence_around_speech_is_cut_but_a_short_gap_stays(self) -> None:
        trimmed = trim_silence(silence(0.26) + tone(1.0) + silence(0.9))
        seconds = len(trimmed) / 2 / SAMPLE_RATE
        assert 1.15 < seconds < 1.25

    def test_speech_itself_is_untouched(self) -> None:
        loud = tone(1.0)
        assert loud in trim_silence(silence(0.5) + loud + silence(0.5))

    def test_quiet_noise_around_the_speech_counts_as_silence(self) -> None:
        noise = np.full(SAMPLE_RATE, 30, dtype=np.int16).tobytes()
        trimmed = trim_silence(noise + tone(0.5) + noise)
        assert len(trimmed) / 2 / SAMPLE_RATE < 0.8

    def test_all_silence_and_empty_audio_are_returned_as_is(self) -> None:
        assert trim_silence(silence(1.0)) == silence(1.0)
        assert trim_silence(b"") == b""


class TestSplitSentences:
    def test_one_sentence_stays_whole(self) -> None:
        assert split_sentences("Hello there, how can I help you today?") == [
            "Hello there, how can I help you today?"
        ]

    def test_short_sentences_are_joined_to_the_next(self) -> None:
        assert split_sentences("Sure. Your appointment is booked for Tuesday at nine.") == [
            "Sure. Your appointment is booked for Tuesday at nine."
        ]

    def test_a_short_last_sentence_joins_the_previous_one(self) -> None:
        parts = split_sentences("Your appointment is booked for Tuesday at nine. Goodbye.")
        assert parts == ["Your appointment is booked for Tuesday at nine. Goodbye."]

    def test_there_are_at_most_four_parts(self) -> None:
        text = " ".join(f"This is sentence number {n} of the reply." for n in range(9))
        assert len(split_sentences(text)) == 4

    def test_dr_is_not_the_end_of_a_sentence(self) -> None:
        text = (
            "Your appointment is confirmed with Dr. Suresh Patel on Tuesday. Please arrive early."
        )
        assert split_sentences(text, min_chars=10) == [
            "Your appointment is confirmed with Dr. Suresh Patel on Tuesday.",
            "Please arrive early.",
        ]

    @pytest.mark.parametrize("abbreviation", ["Mr.", "Mrs.", "Ms.", "Prof.", "A.", "9 a.m.", "No."])
    def test_other_abbreviations_are_not_sentence_ends(self, abbreviation: str) -> None:
        text = f"Please see {abbreviation} Sharma tomorrow morning at the clinic downstairs."
        assert split_sentences(text, min_chars=5) == [text]

    def test_hindi_sentence_ends_split(self) -> None:
        text = "आपका अपॉइंटमेंट मंगलवार को सुबह नौ बजे बुक हो गया है। कृपया पंद्रह मिनट पहले पहुँचिए।"
        assert len(split_sentences(text)) == 2


class TestAudioUtils:
    def test_normalise_silence_unchanged(self) -> None:
        from telephony.audio_utils import normalise_audio

        silent = b"\x00" * 3200
        assert normalise_audio(silent) == silent

    def test_normalise_amplifies_quiet_signal(self) -> None:
        import numpy as np

        from telephony.audio_utils import normalise_audio, pcm_to_float

        samples = (np.ones(1600, dtype=np.float32) * 0.001 * 32767).astype(np.int16)
        pcm = samples.tobytes()
        result = normalise_audio(pcm)
        result_arr = pcm_to_float(result)
        original_arr = pcm_to_float(pcm)
        assert float(result_arr.max()) > float(original_arr.max())

    def test_high_pass_returns_same_length(self) -> None:
        import numpy as np

        from telephony.audio_utils import apply_high_pass

        samples = (np.random.randn(3200) * 1000).astype(np.int16)
        pcm = samples.tobytes()
        result = apply_high_pass(pcm)
        assert len(result) == len(pcm)

    def test_detect_silence_on_zeros(self) -> None:
        from telephony.audio_utils import detect_silence

        assert detect_silence(b"\x00" * 3200) is True

    def test_detect_silence_on_tone(self) -> None:
        import numpy as np

        from telephony.audio_utils import detect_silence

        t = np.linspace(0, 1, 16000)
        samples = (np.sin(2 * 3.14159 * 440 * t) * 30000).astype(np.int16)
        assert detect_silence(samples.tobytes()) is False


class TestPiperSampleRate:
    @pytest.mark.asyncio
    async def test_piper_output_is_resampled_to_16k(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import json

        import telephony.config as cfg_module

        (tmp_path / "voice.onnx").write_bytes(b"")
        (tmp_path / "voice.onnx.json").write_text(json.dumps({"audio": {"sample_rate": 22050}}))
        settings = cfg_module.get_settings()
        monkeypatch.setattr(settings, "piper_models_dir", str(tmp_path))
        monkeypatch.setattr(settings, "piper_voice_en", "voice")

        one_second_native = b"\x10\x00" * 22050

        class FakeProcess:
            returncode = 0

            async def communicate(self, input: bytes) -> tuple[bytes, bytes]:
                return one_second_native, b""

        async def fake_exec(*args: object, **kwargs: object) -> FakeProcess:
            return FakeProcess()

        monkeypatch.setattr("asyncio.create_subprocess_exec", fake_exec)
        pcm = await PiperTTS().synthesize("Hello", "en")
        assert len(pcm) == 16000 * 2


class TestAudioProcessorStreaming:
    def test_high_pass_is_continuous_across_chunks(self) -> None:
        import numpy as np

        from telephony.audio_utils import AudioProcessor

        signal = (np.sin(np.arange(3200) / 5) * 8000 + 3000).astype(np.int16).tobytes()
        whole = AudioProcessor().process(signal)
        streamed = AudioProcessor()
        chunks = b"".join(streamed.process(signal[i : i + 640]) for i in range(0, len(signal), 640))
        assert (
            np.abs(
                np.frombuffer(chunks, np.int16).astype(int) - np.frombuffer(whole, np.int16)
            ).max()
            <= 1
        )

    def test_quiet_line_noise_is_not_boosted(self) -> None:
        import numpy as np

        from telephony.audio_utils import AudioProcessor

        rng = np.random.default_rng(0)
        hiss = (rng.normal(0, 30, 320)).astype(np.int16).tobytes()
        out = np.frombuffer(AudioProcessor().process(hiss), np.int16)
        assert np.abs(out).max() < 200
