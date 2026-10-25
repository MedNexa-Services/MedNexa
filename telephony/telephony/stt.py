"""Speech-to-Text engine using Faster-Whisper.

Faster-Whisper is a CTranslate2-based reimplementation of Whisper that runs
~4x faster on CPU and 2x faster on GPU vs. the original OpenAI Whisper.

This module provides:
  - ``FasterWhisperSTT``: main engine class (singleton-friendly)
  - ``TranscriptionResult``: typed output with text + detected language

Language detection strategy (task 3.5):
  - Faster-Whisper returns a ``language`` field on every transcription.
  - We normalise it to "en" or "hi" (the two supported languages).
  - Any other language is treated as "en" (English default).
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np

from telephony.config import get_settings
from telephony.logging_setup import get_logger

log = get_logger("stt")

# Languages the system officially supports.
SUPPORTED_LANGUAGES = {"en", "hi"}
DEFAULT_LANGUAGE = "en"


@dataclass
class TranscriptionResult:
    text: str
    language: str  # normalised: "en" or "hi"
    confidence: float  # average log-prob converted to [0, 1]
    duration_seconds: float


class FasterWhisperSTT:
    """Faster-Whisper STT engine.

    The model is downloaded on first instantiation (~1.5 GB for large-v3) and
    cached in ~/.cache/huggingface by default.  Use ``whisper_model_size``
    in config to use a smaller model during development.

    One instance can be shared across concurrent calls because Faster-Whisper
    is thread-safe for inference.
    """

    _instance: "FasterWhisperSTT | None" = None

    def __init__(self) -> None:
        cfg = get_settings()
        self._model_size = cfg.whisper_model_size
        self._device = self._resolve_device(cfg.whisper_device)
        self._compute_type = cfg.whisper_compute_type
        self._beam_size = cfg.whisper_beam_size
        self._vad_filter = cfg.whisper_vad_filter
        self._model: Any = None  # lazy-loaded

    @staticmethod
    def _resolve_device(device: str) -> str:
        if device != "auto":
            return device
        try:
            import torch  # type: ignore[import-untyped]
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _load(self) -> None:
        if self._model is not None:
            return
        from faster_whisper import WhisperModel  # type: ignore[import-untyped]
        log.info(
            "whisper_loading",
            model=self._model_size,
            device=self._device,
            compute_type=self._compute_type,
        )
        self._model = WhisperModel(
            self._model_size,
            device=self._device,
            compute_type=self._compute_type,
        )
        log.info("whisper_loaded", model=self._model_size)

    # ── public API ────────────────────────────────────────────────────────────

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        *,
        language_hint: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe raw PCM audio bytes (16 kHz, mono, int16 LE).

        ``language_hint`` can be "en" or "hi" to bias Whisper when the
        caller's language has already been detected in a previous turn.
        """
        self._load()
        import numpy as np  # noqa: PLC0415

        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return self._transcribe_array(samples, language_hint=language_hint)

    def transcribe_file(
        self,
        path: Path | str,
        *,
        language_hint: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe an audio file (WAV/MP3/etc). Mainly for testing."""
        self._load()
        import soundfile as sf  # type: ignore[import-untyped]
        samples, _ = sf.read(str(path), dtype="float32", always_2d=False)
        if samples.ndim == 2:
            samples = samples.mean(axis=1)
        return self._transcribe_array(samples, language_hint=language_hint)

    # ── internals ─────────────────────────────────────────────────────────────

    def _transcribe_array(
        self,
        samples: "np.ndarray[Any, Any]",
        *,
        language_hint: str | None,
    ) -> TranscriptionResult:
        if len(samples) == 0:
            return TranscriptionResult(
                text="", language=language_hint or DEFAULT_LANGUAGE, confidence=0.0, duration_seconds=0.0
            )

        kwargs: dict[str, Any] = {
            "beam_size": self._beam_size,
            "vad_filter": self._vad_filter,
            "word_timestamps": False,
        }
        # If we already know the language, tell Whisper to skip detection.
        if language_hint and language_hint in SUPPORTED_LANGUAGES:
            kwargs["language"] = language_hint

        segments, info = self._model.transcribe(samples, **kwargs)
        segments = list(segments)

        text = " ".join(s.text.strip() for s in segments if s.text.strip())
        language = self._normalise_language(info.language)
        avg_logprob = (
            sum(s.avg_logprob for s in segments) / len(segments) if segments else -1.0
        )
        # Convert log-prob to rough [0, 1] confidence (−1 → ~0.37, 0 → 1.0)
        confidence = float(min(1.0, max(0.0, 1.0 + avg_logprob)))
        duration = float(info.duration) if hasattr(info, "duration") else len(samples) / 16000.0

        log.info(
            "transcribed",
            text=text[:80],
            language=language,
            confidence=round(confidence, 2),
            duration_s=round(duration, 2),
        )
        return TranscriptionResult(
            text=text,
            language=language,
            confidence=confidence,
            duration_seconds=duration,
        )

    @staticmethod
    def _normalise_language(raw: str | None) -> str:
        """Map Whisper's language code to 'en' or 'hi'."""
        if raw is None:
            return DEFAULT_LANGUAGE
        lang = raw.lower()
        if lang.startswith("hi"):
            return "hi"
        if lang in SUPPORTED_LANGUAGES:
            return lang
        return DEFAULT_LANGUAGE
