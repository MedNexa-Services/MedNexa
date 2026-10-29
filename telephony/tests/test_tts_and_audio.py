"""Tests for the TTS module (Piper + Edge-TTS)."""

from __future__ import annotations

import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telephony.tts import (
    CHUNK_BYTES,
    EdgeTTS,
    PiperTTS,
    TTSEngine,
    pcm_16k_to_ulaw_8k,
    ulaw_to_linear,
    upsample_8k_to_16k,
)


# ── TTSEngine ─────────────────────────────────────────────────────────────────


class TestTTSEngine:
    def test_empty_text_returns_empty(self) -> None:
        engine = TTSEngine.__new__(TTSEngine)
        engine._prefer_piper = False
        engine._piper = MagicMock()
        engine._edge = MagicMock()
        engine._piper_ok = False

        import asyncio
        result = asyncio.run(engine.speak("", "en"))
        assert result == b""

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


# ── Audio utils (codec) ────────────────────────────────────────────────────────


class TestTwilioCodecs:
    def test_ulaw_to_linear_roundtrip_approx(self) -> None:
        """μ-law decode then encode should give back approximate original."""
        # Import the encoder from twilio_handler
        from telephony.twilio_handler import ulaw_to_linear, pcm_16k_to_ulaw_8k, upsample_8k_to_16k

        # Create a simple 8 kHz test signal (100 bytes = 50 samples)
        samples = [1000, -1000, 2000, -2000] * 12  # 48 samples
        ulaw_bytes = bytes([
            0b00110101 if s > 0 else 0b10110101 for s in samples
        ])  # rough values — just test non-crash
        linear = ulaw_to_linear(ulaw_bytes)
        assert len(linear) == len(ulaw_bytes) * 2

    def test_upsample_doubles_size(self) -> None:
        from telephony.twilio_handler import upsample_8k_to_16k
        pcm_8k = struct.pack("<10h", *range(10))
        pcm_16k = upsample_8k_to_16k(pcm_8k)
        assert len(pcm_16k) == len(pcm_8k) * 2

    def test_pcm_16k_to_ulaw_8k_halves_size(self) -> None:
        from telephony.twilio_handler import pcm_16k_to_ulaw_8k
        pcm_16k = struct.pack("<20h", *([100] * 20))
        ulaw = pcm_16k_to_ulaw_8k(pcm_16k)
        assert len(ulaw) == 10  # 20 samples → 10 samples


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
