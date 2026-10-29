"""Tests for the TTS module (Piper + Edge-TTS)."""

from __future__ import annotations

import struct
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telephony.tts import (
    CHUNK_BYTES,
    EdgeTTS,
    PiperTTS,
    TTSEngine,
)


# ── TTSEngine ─────────────────────────────────────────────────────────────────


class TestTTSEngine:
    @pytest.mark.asyncio
    async def test_empty_text_returns_empty(self) -> None:
        engine = TTSEngine.__new__(TTSEngine)
        engine._prefer_piper = False
        engine._piper = MagicMock()
        engine._edge = MagicMock()
        engine._piper_ok = False

        assert await engine.speak("", "en") == b""

    @pytest.mark.asyncio
    async def test_falls_back_to_edge_when_piper_unavailable(self) -> None:
        engine = TTSEngine.__new__(TTSEngine)
        engine._prefer_piper = True
        engine._piper_ok = False  # piper not available
        engine._piper = MagicMock()
        edge_mock = AsyncMock()
        edge_mock.synthesize = AsyncMock(return_value=b"\x00" * 100)
        engine._edge = edge_mock

        result = await engine.speak("Hello", "en")
        assert result == b"\x00" * 100
        edge_mock.synthesize.assert_called_once_with("Hello", "en")

    @pytest.mark.asyncio
    async def test_uses_piper_when_available(self) -> None:
        engine = TTSEngine.__new__(TTSEngine)
        engine._prefer_piper = True
        engine._piper_ok = True
        piper_mock = AsyncMock()
        piper_mock.synthesize = AsyncMock(return_value=b"\x01" * 200)
        engine._piper = piper_mock
        engine._edge = AsyncMock()

        result = await engine.speak("Namaste", "hi")
        assert result == b"\x01" * 200
        piper_mock.synthesize.assert_called_once_with("Namaste", "hi")

    @pytest.mark.asyncio
    async def test_piper_failure_falls_back_to_edge(self) -> None:
        engine = TTSEngine.__new__(TTSEngine)
        engine._prefer_piper = True
        engine._piper_ok = True
        piper_mock = AsyncMock()
        piper_mock.synthesize = AsyncMock(side_effect=RuntimeError("piper crashed"))
        engine._piper = piper_mock
        edge_mock = AsyncMock()
        edge_mock.synthesize = AsyncMock(return_value=b"\x02" * 50)
        engine._edge = edge_mock

        result = await engine.speak("Test", "en")
        assert result == b"\x02" * 50
        assert engine._piper_ok is False  # should be disabled after failure

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self) -> None:
        engine = TTSEngine.__new__(TTSEngine)
        engine._prefer_piper = False
        engine._piper_ok = False
        engine._piper = MagicMock()
        edge_mock = AsyncMock()
        # Return 2x CHUNK_BYTES of audio
        edge_mock.synthesize = AsyncMock(return_value=b"\x00" * (CHUNK_BYTES * 2))
        engine._edge = edge_mock

        chunks = []
        async for chunk in engine.stream("Hello world", "en"):
            chunks.append(chunk)

        assert len(chunks) == 2
        assert all(len(c) == CHUNK_BYTES for c in chunks)


# The μ-law codec is tested in tests/test_audio_codec.py.


# ── Audio quality ──────────────────────────────────────────────────────────────


class TestAudioUtils:
    def test_normalise_silence_unchanged(self) -> None:
        from telephony.audio_utils import normalise_audio
        silent = b"\x00" * 3200
        assert normalise_audio(silent) == silent

    def test_normalise_amplifies_quiet_signal(self) -> None:
        import numpy as np
        from telephony.audio_utils import normalise_audio, pcm_to_float

        # Very quiet signal
        samples = (np.ones(1600, dtype=np.float32) * 0.001 * 32767).astype(np.int16)
        pcm = samples.tobytes()
        result = normalise_audio(pcm)
        result_arr = pcm_to_float(result)
        original_arr = pcm_to_float(pcm)
        # The normalised version should be louder
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
        """Piper voices speak at their own rate (22050 Hz for *-medium voices)."""
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
        assert len(pcm) == 16000 * 2  # still one second, now at 16 kHz


class TestAudioProcessorStreaming:
    def test_high_pass_is_continuous_across_chunks(self) -> None:
        """Filtering a stream chunk by chunk must equal filtering it in one go."""
        import numpy as np

        from telephony.audio_utils import AudioProcessor

        signal = (np.sin(np.arange(3200) / 5) * 8000 + 3000).astype(np.int16).tobytes()
        whole = AudioProcessor().process(signal)
        streamed = AudioProcessor()
        chunks = b"".join(streamed.process(signal[i : i + 640]) for i in range(0, len(signal), 640))
        assert np.abs(
            np.frombuffer(chunks, np.int16).astype(int) - np.frombuffer(whole, np.int16)
        ).max() <= 1

    def test_quiet_line_noise_is_not_boosted(self) -> None:
        import numpy as np

        from telephony.audio_utils import AudioProcessor

        rng = np.random.default_rng(0)
        hiss = (rng.normal(0, 30, 320)).astype(np.int16).tobytes()  # ~-60 dBFS noise
        out = np.frombuffer(AudioProcessor().process(hiss), np.int16)
        assert np.abs(out).max() < 200  # per-chunk normalisation made this ~3000
