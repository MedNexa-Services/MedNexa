from __future__ import annotations

from typing import Final

import numpy as np

from telephony.logging_setup import get_logger

log = get_logger("audio")

SAMPLE_RATE: Final[int] = 16000
INT16_MAX: Final[float] = 32767.0

TARGET_RMS_FRACTION: Final[float] = 0.1


def pcm_to_float(raw: bytes) -> np.ndarray[np.float32, np.dtype[np.float32]]:
    arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    return arr / INT16_MAX


def float_to_pcm(arr: np.ndarray[np.float32, np.dtype[np.float32]]) -> bytes:
    clipped = np.clip(arr, -1.0, 1.0)
    return (clipped * INT16_MAX).astype(np.int16).tobytes()


def normalise_audio(raw: bytes, *, target_rms: float = TARGET_RMS_FRACTION) -> bytes:
    if not raw:
        return raw
    arr = pcm_to_float(raw)
    rms = float(np.sqrt(np.mean(arr**2)))
    if rms < 1e-6:
        return raw
    gain = min(target_rms / rms, 10.0)
    return float_to_pcm(arr * gain)


def _high_pass_alpha(cutoff_hz: float) -> float:
    rc = 1.0 / (2 * np.pi * cutoff_hz)
    dt = 1.0 / SAMPLE_RATE
    return rc / (rc + dt)


def _high_pass(
    arr: np.ndarray[np.float32, np.dtype[np.float32]],
    alpha: float,
    prev_x: float,
    prev_y: float,
) -> tuple[np.ndarray[np.float32, np.dtype[np.float32]], float, float]:
    filtered = np.empty_like(arr)
    for i, x in enumerate(arr):
        prev_y = alpha * (prev_y + x - prev_x)
        prev_x = float(x)
        filtered[i] = prev_y
    return filtered, prev_x, prev_y


def apply_high_pass(raw: bytes, *, cutoff_hz: float = 80.0) -> bytes:
    if not raw:
        return raw
    arr = pcm_to_float(raw)
    filtered, _, _ = _high_pass(arr, _high_pass_alpha(cutoff_hz), float(arr[0]), 0.0)
    return float_to_pcm(filtered)


def detect_silence(raw: bytes, *, threshold: float = 0.01) -> bool:
    if not raw:
        return True
    arr = pcm_to_float(raw)
    rms = float(np.sqrt(np.mean(arr**2)))
    return rms < threshold


class AudioProcessor:
    def __init__(
        self,
        *,
        enable_high_pass: bool = True,
        enable_normalise: bool = False,
        target_rms: float = TARGET_RMS_FRACTION,
        hp_cutoff_hz: float = 80.0,
    ) -> None:
        self._hp = enable_high_pass
        self._norm = enable_normalise
        self._target_rms = target_rms
        self._alpha = _high_pass_alpha(hp_cutoff_hz)
        self._prev_x: float | None = None
        self._prev_y = 0.0

    def process(self, raw: bytes) -> bytes:
        if not raw:
            return raw
        out = raw
        if self._hp:
            arr = pcm_to_float(out)
            prev_x = float(arr[0]) if self._prev_x is None else self._prev_x
            filtered, self._prev_x, self._prev_y = _high_pass(
                arr, self._alpha, prev_x, self._prev_y
            )
            out = float_to_pcm(filtered)
        if self._norm:
            out = normalise_audio(out, target_rms=self._target_rms)
        return out
