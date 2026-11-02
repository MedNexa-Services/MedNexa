from __future__ import annotations

import numpy as np
import pytest

from telephony.vad import FRAME_BYTES, FRAME_SAMPLES, SileroVAD


def make_silence(n_frames: int = 10) -> bytes:
    return b"\x00" * FRAME_BYTES * n_frames


def make_tone(frequency_hz: float = 440.0, n_frames: int = 20) -> bytes:
    n_samples = FRAME_SAMPLES * n_frames
    t = np.linspace(0, n_samples / 16000, n_samples, endpoint=False)
    samples = (np.sin(2 * np.pi * frequency_hz * t) * 32000).astype(np.int16)
    return samples.tobytes()


class TestVadHelpers:
    def test_frame_constants(self) -> None:
        assert FRAME_BYTES == FRAME_SAMPLES * 2
        assert FRAME_SAMPLES == 512

    def test_silence_produces_silence_events(self, monkeypatch: pytest.MonkeyPatch) -> None:
        vad = SileroVAD.__new__(SileroVAD)
        vad._threshold = 0.5
        vad._min_speech_ms = 250
        vad._min_silence_ms = 600
        vad._sample_rate = 16000
        vad._in_speech = False
        vad._speech_start_ms = 0.0
        vad._silence_start_ms = 0.0
        vad._elapsed_ms = 0.0
        vad._leftover = b""

        monkeypatch.setattr(vad, "_is_speech_frame", lambda samples: False)

        events = vad.process_chunk(make_silence(5))
        assert all(e == "silence" for e in events)

    def test_speech_start_detected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        vad = SileroVAD.__new__(SileroVAD)
        vad._threshold = 0.5
        vad._min_speech_ms = 250
        vad._min_silence_ms = 600
        vad._sample_rate = 16000
        vad._in_speech = False
        vad._speech_start_ms = 0.0
        vad._silence_start_ms = 0.0
        vad._elapsed_ms = 0.0
        vad._leftover = b""

        call_count = [0]

        def mock_speech(samples: object) -> bool:
            call_count[0] += 1
            return True

        monkeypatch.setattr(vad, "_is_speech_frame", mock_speech)

        events = vad.process_chunk(make_tone(n_frames=5))
        assert "speech_start" in events
        assert all(e in ("speech_start", "speech") for e in events)

    def test_speech_end_after_silence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        vad = SileroVAD.__new__(SileroVAD)
        vad._threshold = 0.5
        vad._min_speech_ms = 250
        vad._min_silence_ms = 600
        vad._sample_rate = 16000
        vad._in_speech = True
        vad._speech_start_ms = 0.0
        vad._silence_start_ms = 0.0
        vad._elapsed_ms = 500.0
        vad._leftover = b""

        def mock_silence(samples: object) -> bool:
            return False

        monkeypatch.setattr(vad, "_is_speech_frame", mock_silence)

        events = vad.process_chunk(make_silence(25))
        assert "speech_end" in events
        assert not vad._in_speech

    def test_reset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        vad = SileroVAD.__new__(SileroVAD)
        vad._threshold = 0.5
        vad._min_speech_ms = 250
        vad._min_silence_ms = 600
        vad._sample_rate = 16000
        vad._in_speech = True
        vad._speech_start_ms = 100.0
        vad._silence_start_ms = 200.0
        vad._elapsed_ms = 999.0
        vad._leftover = b"\x00" * 10

        vad.reset()

        assert not vad._in_speech
        assert vad._elapsed_ms == 0.0
        assert vad._leftover == b""

    def test_leftover_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        vad = SileroVAD.__new__(SileroVAD)
        vad._threshold = 0.5
        vad._min_speech_ms = 250
        vad._min_silence_ms = 600
        vad._sample_rate = 16000
        vad._in_speech = False
        vad._speech_start_ms = 0.0
        vad._silence_start_ms = 0.0
        vad._elapsed_ms = 0.0
        vad._leftover = b""

        monkeypatch.setattr(vad, "_is_speech_frame", lambda s: False)

        half_frame = make_silence(1)[: FRAME_BYTES // 2]
        events1 = vad.process_chunk(half_frame)
        assert events1 == []
        assert len(vad._leftover) == len(half_frame)

        events2 = vad.process_chunk(half_frame)
        assert events2 == ["silence"]
        assert vad._leftover == b""
