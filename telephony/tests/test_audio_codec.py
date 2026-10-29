"""G.711 μ-law codec and resampling."""

from __future__ import annotations

import numpy as np
import pytest

from telephony.audio_codec import (
    pcm16_to_ulaw,
    pipeline_to_twilio,
    resample,
    twilio_to_pipeline,
    ulaw_to_pcm16,
)


def pcm(*samples: int) -> bytes:
    return np.array(samples, dtype="<i2").tobytes()


def samples(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype="<i2").astype(np.int32)


@pytest.mark.parametrize("amplitude", [0, 50, 100, 1000, 5000, 20000, 32767, -100, -20000])
def test_ulaw_round_trip_is_within_g711_quantisation(amplitude: int) -> None:
    decoded = samples(ulaw_to_pcm16(pcm16_to_ulaw(pcm(amplitude))))[0]
    # μ-law step size is ~1/16 of the magnitude (plus the small bias near zero).
    assert abs(decoded - amplitude) <= max(8, abs(amplitude) // 16)


def test_ulaw_known_codes() -> None:
    # G.711: 0xFF and 0x7F are the two zero codes; 0x00 / 0x80 are the extremes.
    assert samples(ulaw_to_pcm16(bytes([0xFF, 0x7F]))).tolist() == [0, 0]
    assert samples(ulaw_to_pcm16(bytes([0x00, 0x80]))).tolist() == [-32124, 32124]
    assert pcm16_to_ulaw(pcm(0)) == bytes([0xFF])


def test_every_code_decodes_and_re_encodes_to_itself() -> None:
    codes = bytes(c for c in range(256) if c != 0x7F)  # 0x7F (-0) re-encodes as 0xFF (+0)
    assert pcm16_to_ulaw(ulaw_to_pcm16(codes)) == codes


def test_resample_lengths() -> None:
    one_second_8k = pcm(*([1000] * 8000))
    assert len(resample(one_second_8k, 8000, 16000)) == 16000 * 2
    assert len(resample(pcm(*([1000] * 22050)), 22050, 16000)) == 16000 * 2
    assert resample(one_second_8k, 8000, 8000) == one_second_8k


def test_resample_preserves_a_tone() -> None:
    t = np.arange(22050) / 22050
    tone = (np.sin(2 * np.pi * 440 * t) * 10000).astype("<i2").tobytes()
    out = samples(resample(tone, 22050, 16000))
    expected = np.sin(2 * np.pi * 440 * np.arange(16000) / 16000) * 10000
    assert np.abs(out[100:-100] - expected[100:-100]).max() < 600


def test_twilio_round_trip_keeps_speech_band_signal() -> None:
    t = np.arange(1600) / 16000  # 100 ms at 16 kHz
    tone = (np.sin(2 * np.pi * 300 * t) * 8000).astype("<i2").tobytes()
    ulaw = pipeline_to_twilio(tone)
    assert len(ulaw) == 800  # 8 kHz, one byte per sample
    back = samples(twilio_to_pipeline(ulaw))
    original = samples(tone)
    correlation = np.corrcoef(back[50:-50], original[50:-50])[0, 1]
    assert correlation > 0.99
