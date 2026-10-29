"""Tests for the STT module (Faster-Whisper wrapper)."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from telephony.stt import DEFAULT_LANGUAGE, FasterWhisperSTT, TranscriptionResult


class TestLanguageNormalisation:
    def test_english(self) -> None:
        assert FasterWhisperSTT._normalise_language("en") == "en"
        assert FasterWhisperSTT._normalise_language("English") == "en"

    def test_hindi(self) -> None:
        assert FasterWhisperSTT._normalise_language("hi") == "hi"
        assert FasterWhisperSTT._normalise_language("Hindi") == "hi"

    def test_unknown_falls_back_to_english(self) -> None:
        assert FasterWhisperSTT._normalise_language("fr") == DEFAULT_LANGUAGE
        assert FasterWhisperSTT._normalise_language(None) == DEFAULT_LANGUAGE
        assert FasterWhisperSTT._normalise_language("zh") == DEFAULT_LANGUAGE

    def test_hindi_prefix(self) -> None:
        # Whisper sometimes returns "hindi" (full name)
        assert FasterWhisperSTT._normalise_language("hindi") == "hi"


class TestTranscribeBytes:
    """Test transcribe_bytes with a mocked Whisper model."""

    def _make_pcm(self, duration_s: float = 1.0) -> bytes:
        """Generate silent PCM audio."""
        n = int(16000 * duration_s)
        return (np.zeros(n, dtype=np.int16)).tobytes()

    def test_empty_bytes_returns_empty(self) -> None:
        stt = FasterWhisperSTT.__new__(FasterWhisperSTT)
        stt._model = None
        result = stt.transcribe_bytes(b"")
        assert result.text == ""
        assert result.confidence == 0.0

    def test_transcribe_mocked(self) -> None:
        """Verify transcribe_bytes passes through model output correctly."""
        stt = FasterWhisperSTT.__new__(FasterWhisperSTT)
        stt._model_size = "base"
        stt._device = "cpu"
        stt._compute_type = "int8"
        stt._beam_size = 1
        stt._vad_filter = False
        stt._model = None

        # Build mock segment and info
        mock_segment = MagicMock()
        mock_segment.text = "  Hello, how can I help?  "
        mock_segment.avg_logprob = -0.1

        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.duration = 2.0

        with patch.object(stt, "_load"):
            with patch.object(
                stt, "_transcribe_array",
                return_value=TranscriptionResult(
                    text="Hello, how can I help?",
                    language="en",
                    confidence=0.9,
                    duration_seconds=2.0,
                )
            ):
                result = stt.transcribe_bytes(self._make_pcm(2.0))

        assert result.text == "Hello, how can I help?"
        assert result.language == "en"
        assert result.confidence > 0

    def test_hindi_hint_preserved(self) -> None:
        """Language hint should be passed through when provided."""
        stt = FasterWhisperSTT.__new__(FasterWhisperSTT)
        stt._model_size = "base"
        stt._device = "cpu"
        stt._compute_type = "int8"
        stt._beam_size = 1
        stt._vad_filter = False
        stt._model = None

        captured: dict[str, object] = {}

        def fake_transcribe(
            samples: object, *, language_hint: str | None
        ) -> TranscriptionResult:
            captured["hint"] = language_hint
            return TranscriptionResult(
                text="नमस्ते", language="hi", confidence=0.85, duration_seconds=1.0
            )

        with patch.object(stt, "_load"):
            with patch.object(stt, "_transcribe_array", side_effect=fake_transcribe):
                stt.transcribe_bytes(self._make_pcm(), language_hint="hi")

        assert captured["hint"] == "hi"


class TestDeviceResolution:
    def test_explicit_cpu(self) -> None:
        assert FasterWhisperSTT._resolve_device("cpu") == "cpu"

    def test_explicit_cuda(self) -> None:
        assert FasterWhisperSTT._resolve_device("cuda") == "cuda"

    def test_auto_no_cuda(self) -> None:
        with patch("torch.cuda.is_available", return_value=False):
            assert FasterWhisperSTT._resolve_device("auto") == "cpu"

    def test_auto_with_cuda(self) -> None:
        with patch("torch.cuda.is_available", return_value=True):
            assert FasterWhisperSTT._resolve_device("auto") == "cuda"


class FakeWhisper:
    """Stands in for faster_whisper.WhisperModel; records each transcribe call."""

    def __init__(self, detected: str, probs: list[tuple[str, float]] | None = None) -> None:
        self.detected = detected
        self.probs = probs or []
        self.calls: list[dict[str, object]] = []

    def transcribe(self, samples: object, **kwargs: object) -> tuple[list[MagicMock], MagicMock]:
        self.calls.append(kwargs)
        segment = MagicMock(text=" text ", avg_logprob=-0.2)
        info = MagicMock(duration=1.0, all_language_probs=self.probs)
        info.language = kwargs.get("language") or self.detected
        return [segment], info


def make_stt(model: FakeWhisper) -> FasterWhisperSTT:
    stt = FasterWhisperSTT.__new__(FasterWhisperSTT)
    stt._beam_size, stt._vad_filter, stt._model = 1, False, model
    return stt


PCM = (np.ones(16000, dtype=np.int16) * 100).tobytes()


class TestLanguageDetection:
    def test_language_is_detected_not_forced(self) -> None:
        model = FakeWhisper("hi")
        assert make_stt(model).transcribe_bytes(PCM).language == "hi"
        assert "language" not in model.calls[0]

    def test_urdu_label_means_hindi(self) -> None:
        model = FakeWhisper("ur")
        assert make_stt(model).transcribe_bytes(PCM).language == "hi"
        assert len(model.calls) == 1

    def test_unsupported_language_is_redone_as_the_likelier_one(self) -> None:
        model = FakeWhisper("ne", probs=[("ne", 0.5), ("hi", 0.3), ("en", 0.1)])
        result = make_stt(model).transcribe_bytes(PCM)
        assert result.language == "hi"
        assert model.calls[1]["language"] == "hi"

    def test_explicit_hint_is_still_honoured(self) -> None:
        model = FakeWhisper("en")
        assert make_stt(model).transcribe_bytes(PCM, language_hint="hi").language == "hi"
        assert model.calls[0]["language"] == "hi"


def test_whisper_model_is_loaded_once_and_shared(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys
    import types

    built: list[tuple[object, ...]] = []
    fake_module = types.ModuleType("faster_whisper")
    fake_module.WhisperModel = lambda *a, **kw: built.append(a) or object()  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    monkeypatch.setattr(FasterWhisperSTT, "_models", {})

    first, second = FasterWhisperSTT(), FasterWhisperSTT()
    first._load()
    second._load()
    assert len(built) == 1
    assert first._model is second._model
