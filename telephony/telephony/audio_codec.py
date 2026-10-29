"""Audio format conversion: G.711 μ-law (Twilio, 8 kHz) <-> 16-bit PCM, and resampling.

The pipeline works in 16 kHz mono int16 PCM. Twilio Media Streams carry 8 kHz
μ-law, and Piper voices produce their own native rate (often 22050 Hz).
Everything is vectorised with numpy: these run on every audio chunk of every call.
"""

from __future__ import annotations

import numpy as np

_BIAS = 0x84
_CLIP = 32635


def _build_decode_table() -> np.ndarray:  # type: ignore[type-arg]
    codes = ~np.arange(256, dtype=np.int32) & 0xFF
    exponent = (codes >> 4) & 0x07
    mantissa = codes & 0x0F
    magnitude = (((mantissa << 3) + _BIAS) << exponent) - _BIAS
    return np.where(codes & 0x80, -magnitude, magnitude).astype(np.int16)


_DECODE = _build_decode_table()


def ulaw_to_pcm16(data: bytes) -> bytes:
    """Decode G.711 μ-law bytes to int16 little-endian PCM (same sample rate)."""
    return _DECODE[np.frombuffer(data, dtype=np.uint8)].tobytes()


def pcm16_to_ulaw(pcm: bytes) -> bytes:
    """Encode int16 little-endian PCM to G.711 μ-law (same sample rate)."""
    x = np.frombuffer(pcm, dtype="<i2").astype(np.int32)
    sign = np.where(x < 0, 0x80, 0)
    magnitude = np.minimum(np.abs(x), _CLIP) + _BIAS  # 132 .. 32767
    exponent = np.clip(np.floor(np.log2(magnitude)).astype(np.int32) - 7, 0, 7)
    mantissa = (magnitude >> (exponent + 3)) & 0x0F
    return (~(sign | (exponent << 4) | mantissa) & 0xFF).astype(np.uint8).tobytes()


def resample(pcm: bytes, src_rate: int, dst_rate: int) -> bytes:
    """Linear-interpolation resampling of int16 mono PCM.

    Good enough for telephone-band speech; downsampling first averages the
    input over each output step to limit aliasing.
    """
    if src_rate == dst_rate or not pcm:
        return pcm
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
    if dst_rate < src_rate:
        width = max(1, round(src_rate / dst_rate))
        if width > 1:
            samples = np.convolve(samples, np.ones(width) / width, mode="same")
    n_out = int(len(samples) * dst_rate / src_rate)
    positions = np.arange(n_out) * (src_rate / dst_rate)
    out = np.interp(positions, np.arange(len(samples)), samples)
    return np.clip(np.round(out), -32768, 32767).astype("<i2").tobytes()


def twilio_to_pipeline(ulaw_8k: bytes) -> bytes:
    """Twilio inbound media (8 kHz μ-law) -> pipeline audio (16 kHz PCM)."""
    return resample(ulaw_to_pcm16(ulaw_8k), 8000, 16000)


def pipeline_to_twilio(pcm_16k: bytes) -> bytes:
    """Pipeline audio (16 kHz PCM) -> Twilio outbound media (8 kHz μ-law)."""
    return pcm16_to_ulaw(resample(pcm_16k, 16000, 8000))
