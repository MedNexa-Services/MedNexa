"""Voice Activity Detection using Silero VAD.

Silero VAD is a lightweight PyTorch model (~1 MB) that detects speech/silence
in 16 kHz mono audio frames. We use it to:
  1. Detect when the caller starts speaking (speech_start).
  2. Detect when they finish (speech_end — silence after speech).
  3. Implement barge-in: interrupt TTS when speech is detected.

Usage::

    vad = SileroVAD()                    # loads model on first call
    for chunk in audio_stream:
        result = vad.process_chunk(chunk)
        if result == "speech_start":   ...
        if result == "speech_end":     ...
"""

from __future__ import annotations

from typing import Literal

import numpy as np

from telephony.config import get_settings
from telephony.logging_setup import get_logger

log = get_logger("vad")

# Silero VAD model expects exactly 512 samples at 16 kHz (32 ms frames).
# We accumulate raw bytes and process complete frames.
FRAME_SAMPLES = 512  # 32 ms @ 16 kHz
FRAME_BYTES = FRAME_SAMPLES * 2  # int16 = 2 bytes per sample

VadEvent = Literal["silence", "speech_start", "speech", "speech_end"]


class SileroVAD:
    """Wrapper around the Silero VAD torch model.

    Thread-safe for a single call; create one instance per active call.
    The model is cached as a class-level attribute so it is loaded only once
    across all concurrent calls (saves ~300 ms startup per call).
    """

    _model: object | None = None  # silero model (shared)
    _utils: object | None = None

    @classmethod
    def _load_model(cls) -> tuple[object, object]:
        if cls._model is None:
            import torch  # type: ignore[import-untyped]

            log.info("vad_model_loading", model="silero_vad")
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                onnx=False,
            )
            model.eval()
            cls._model = model
            cls._utils = utils
            log.info("vad_model_loaded")
        return cls._model, cls._utils  # type: ignore[return-value]

    def __init__(self) -> None:
        cfg = get_settings()
        self._threshold: float = cfg.vad_threshold
        self._min_speech_ms: int = cfg.vad_min_speech_ms
        self._min_silence_ms: int = cfg.vad_min_silence_ms
        self._sample_rate: int = cfg.vad_sample_rate

        self._model_obj, self._utils_obj = self._load_model()

        # State machine
        self._in_speech: bool = False
        self._speech_start_ms: float = 0.0
        self._silence_start_ms: float = 0.0
        self._elapsed_ms: float = 0.0  # tracks position in stream
        self._leftover: bytes = b""  # incomplete frame buffer

    def _ms_per_frame(self) -> float:
        return (FRAME_SAMPLES / self._sample_rate) * 1000  # 32 ms

    def _is_speech_frame(self, samples: np.ndarray) -> bool:  # type: ignore[type-arg]
        """Run VAD on one 32 ms frame. Returns True if speech detected."""
        import torch  # type: ignore[import-untyped]

        tensor = torch.from_numpy(samples.astype(np.float32) / 32768.0)
        with torch.no_grad():
            confidence = self._model_obj(tensor, self._sample_rate).item()  # type: ignore[operator]
        return confidence >= self._threshold

    def process_chunk(self, raw_bytes: bytes) -> list[VadEvent]:
        """Process a raw PCM chunk (16-bit little-endian, 16 kHz mono).

        Returns a list of events that occurred in this chunk:
          - ``"speech_start"`` — silence → speech transition
          - ``"speech"``       — continuation of active speech
          - ``"speech_end"``   — speech → silence transition (utterance ready)
          - ``"silence"``      — pure silence (no transition)
        """
        events: list[VadEvent] = []
        buf = self._leftover + raw_bytes

        while len(buf) >= FRAME_BYTES:
            frame_bytes = buf[:FRAME_BYTES]
            buf = buf[FRAME_BYTES:]
            samples = np.frombuffer(frame_bytes, dtype=np.int16)
            is_speech = self._is_speech_frame(samples)
            ms = self._ms_per_frame()

            if is_speech:
                if not self._in_speech:
                    # Was silent — check if this is a speech start
                    self._speech_start_ms = self._elapsed_ms
                    self._in_speech = True
                    events.append("speech_start")
                else:
                    events.append("speech")
                self._silence_start_ms = 0.0
            else:
                if self._in_speech:
                    if self._silence_start_ms == 0.0:
                        self._silence_start_ms = self._elapsed_ms
                    silence_duration = self._elapsed_ms - self._silence_start_ms
                    speech_duration = self._elapsed_ms - self._speech_start_ms
                    if (
                        silence_duration >= self._min_silence_ms
                        and speech_duration >= self._min_speech_ms
                    ):
                        self._in_speech = False
                        self._silence_start_ms = 0.0
                        events.append("speech_end")
                    else:
                        # Still counting as "in speech" — brief pause
                        events.append("speech")
                else:
                    events.append("silence")

            self._elapsed_ms += ms

        self._leftover = buf
        return events

    def reset(self) -> None:
        """Reset state machine for a new utterance."""
        self._in_speech = False
        self._speech_start_ms = 0.0
        self._silence_start_ms = 0.0
        self._elapsed_ms = 0.0
        self._leftover = b""

    @property
    def in_speech(self) -> bool:
        return self._in_speech
