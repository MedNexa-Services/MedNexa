"""pytest configuration for the telephony test suite.

Sets up async test infrastructure and overrides settings so that
tests never touch real external services.
"""

from __future__ import annotations

import pytest

from telephony.config import TelephonySettings


@pytest.fixture(autouse=True)
def override_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override settings for all tests so they never hit real services."""
    import telephony.config as cfg_module

    test_settings = TelephonySettings(
        backend_url="http://test-backend:8000",
        hospital_id="00000000-0000-0000-0000-000000000000",
        whisper_model_size="tiny",
        whisper_device="cpu",
        whisper_compute_type="int8",
        vad_threshold=0.5,
        vad_min_speech_ms=100,
        vad_min_silence_ms=200,
        tts_engine="edge",
        enable_recordings=False,
        call_timeout_seconds=60,
        silence_timeout_seconds=10,
    )
    monkeypatch.setattr(cfg_module, "_settings", test_settings)
