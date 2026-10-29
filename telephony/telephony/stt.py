"""Speech-to-Text engine using Faster-Whisper.

Faster-Whisper is a CTranslate2-based reimplementation of Whisper that runs
~4x faster on CPU and 2x faster on GPU vs. the original OpenAI Whisper.

This module provides:
  - ``FasterWhisperSTT``: main engine class (singleton-friendly)
  - ``TranscriptionResult``: typed output with text + detected language

Language detection strategy (task 3.5):
  - Whisper detects the language of every utterance (it is never forced to the
    previous turn's language, so callers can switch mid-call).
  - "hi" and "ur" (Whisper often labels spoken Hindi as Urdu) map to "hi".
  - Any other detected language is re-transcribed as whichever of en/hi Whisper
    rated more likely.

The Whisper model is loaded once per process and shared by all calls.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from telephony.config import get_settings
from telephony.logging_setup import get_logger

log = get_logger("stt")

# Languages the system officially supports.
SUPPORTED_LANGUAGES = {"en", "hi"}
DEFAULT_LANGUAGE = "en"
# Whisper codes that mean one of our languages.
_LANGUAGE_ALIASES = {"hi": "hi", "ur": "hi", "en": "en"}


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

    # One model per (size, device, compute type), shared by every call in the process.
    _models: dict[tuple[str, str, str], Any] = {}
    _models_lock = threading.Lock()

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
        key = (self._model_size, self._device, self._compute_type)
        with self._models_lock:
            if key not in self._models:
                from faster_whisper import WhisperModel  # type: ignore[import-untyped]

                log.info(
                    "whisper_loading",
                    model=self._model_size,
                    device=self._device,
                    compute_type=self._compute_type,
                )
                self._models[key] = WhisperModel(
                    self._model_size, device=self._device, compute_type=self._compute_type
                )
                log.info("whisper_loaded", model=self._model_size)
        self._model = self._models[key]

    # ── public API ────────────────────────────────────────────────────────────

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        *,
        language_hint: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe raw PCM audio bytes (16 kHz, mono, int16 LE).

        Blocking (CPU/GPU bound): call it from a worker thread in async code.
        ``language_hint`` forces the language ("en"/"hi"); leave it unset so
        Whisper detects the language of each utterance.
        """
        if not audio_bytes:
            return self._empty(language_hint)
        self._load()
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
        samples: np.ndarray[Any, Any],
        *,
        language_hint: str | None,
    ) -> TranscriptionResult:
        if len(samples) == 0:
            return self._empty(language_hint)

        forced = language_hint if language_hint in SUPPORTED_LANGUAGES else None
        segments, info = self._run(samples, forced)
        language = forced or _LANGUAGE_ALIASES.get((info.language or "").lower())
        if language is None:
            # Detected something we don't support: redo it as the likelier of en/hi.
            language = self._likelier_supported(info)
            segments, info = self._run(samples, language)

        text = " ".join(s.text.strip() for s in segments if s.text.strip())
        avg_logprob = sum(s.avg_logprob for s in segments) / len(segments) if segments else -1.0
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

    def _run(self, samples: np.ndarray[Any, Any], language: str | None) -> tuple[list[Any], Any]:
        kwargs: dict[str, Any] = {
            "beam_size": self._beam_size,
            "vad_filter": self._vad_filter,
            "word_timestamps": False,
        }
        if language:
            kwargs["language"] = language
        segments, info = self._model.transcribe(samples, **kwargs)
        return list(segments), info

    @staticmethod
    def _likelier_supported(info: Any) -> str:
        probs = dict(getattr(info, "all_language_probs", None) or [])
        hindi = probs.get("hi", 0.0) + probs.get("ur", 0.0)
        return "hi" if hindi > probs.get("en", 0.0) else DEFAULT_LANGUAGE

    @staticmethod
    def _empty(language_hint: str | None) -> TranscriptionResult:
        return TranscriptionResult(
            text="",
            language=language_hint if language_hint in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE,
            confidence=0.0,
            duration_seconds=0.0,
        )

    @staticmethod
    def _normalise_language(raw: str | None) -> str:
        """Map Whisper's language code to 'en' or 'hi'."""
        if raw is None:
            return DEFAULT_LANGUAGE
        lang = raw.lower()
        if lang.startswith("hi") or lang in ("ur", "urdu"):
            return "hi"
        if lang in SUPPORTED_LANGUAGES:
            return lang
        return DEFAULT_LANGUAGE
