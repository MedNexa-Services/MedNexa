from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from telephony.config import get_settings
from telephony.logging_setup import get_logger

log = get_logger("stt")

SUPPORTED_LANGUAGES = {"en", "hi"}
DEFAULT_LANGUAGE = "en"
_LANGUAGE_ALIASES = {"hi": "hi", "ur": "hi", "en": "en"}


@dataclass
class TranscriptionResult:
    text: str
    language: str
    confidence: float
    duration_seconds: float


class FasterWhisperSTT:
    _models: dict[tuple[str, str, str], Any] = {}
    _models_lock = threading.Lock()

    def __init__(self) -> None:
        cfg = get_settings()
        self._model_size = cfg.whisper_model_size
        self._device = self._resolve_device(cfg.whisper_device)
        self._compute_type = cfg.whisper_compute_type
        self._beam_size = cfg.whisper_beam_size
        self._vad_filter = cfg.whisper_vad_filter
        self._model: Any = None

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

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        *,
        language_hint: str | None = None,
        prompt: str | None = None,
    ) -> TranscriptionResult:
        if not audio_bytes:
            return self._empty(language_hint)
        self._load()
        samples = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        return self._transcribe_array(samples, language_hint=language_hint, prompt=prompt)

    def warm_up(self) -> None:
        self._load()
        noise = np.random.default_rng(0).standard_normal(16000 * 2).astype(np.float32) * 0.01
        segments, _ = self._model.transcribe(noise, language="en", vad_filter=False)
        list(segments)

    def transcribe_file(
        self,
        path: Path | str,
        *,
        language_hint: str | None = None,
    ) -> TranscriptionResult:
        self._load()
        import soundfile as sf  # type: ignore[import-untyped]

        samples, _ = sf.read(str(path), dtype="float32", always_2d=False)
        if samples.ndim == 2:
            samples = samples.mean(axis=1)
        return self._transcribe_array(samples, language_hint=language_hint, prompt=None)

    def _transcribe_array(
        self,
        samples: np.ndarray[Any, Any],
        *,
        language_hint: str | None,
        prompt: str | None,
    ) -> TranscriptionResult:
        if len(samples) == 0:
            return self._empty(language_hint)

        forced = language_hint if language_hint in SUPPORTED_LANGUAGES else None
        segments, info = self._run(samples, forced, prompt)
        language = forced or _LANGUAGE_ALIASES.get((info.language or "").lower())
        if language is None:
            language = self._likelier_supported(info)
            segments, info = self._run(samples, language, prompt)

        segments = [s for s in segments if not (s.no_speech_prob > 0.6 and s.avg_logprob < -1.0)]
        text = " ".join(s.text.strip() for s in segments if s.text.strip())
        avg_logprob = sum(s.avg_logprob for s in segments) / len(segments) if segments else -1.0
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

    def _run(
        self, samples: np.ndarray[Any, Any], language: str | None, prompt: str | None = None
    ) -> tuple[list[Any], Any]:
        kwargs: dict[str, Any] = {
            "beam_size": self._beam_size,
            "vad_filter": self._vad_filter,
            "word_timestamps": False,
            "condition_on_previous_text": False,
        }
        if prompt:
            kwargs["initial_prompt"] = prompt
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
        if raw is None:
            return DEFAULT_LANGUAGE
        lang = raw.lower()
        if lang.startswith("hi") or lang in ("ur", "urdu"):
            return "hi"
        if lang in SUPPORTED_LANGUAGES:
            return lang
        return DEFAULT_LANGUAGE
