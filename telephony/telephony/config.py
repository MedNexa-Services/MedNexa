"""Telephony pipeline configuration.

All variables are prefixed MEDNEXA_TEL_ in the environment / .env file.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelephonySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEDNEXA_TEL_",
        env_file=".env",
        extra="ignore",
    )

    # ── Backend API ──────────────────────────────────────────────────────────
    backend_url: str = "http://localhost:8000"
    """Base URL of the Part 1 FastAPI backend (no trailing slash)."""

    hospital_id: str = ""
    """UUID of the hospital this pipeline serves. Set in .env."""

    use_stub_agent: bool = False
    """Use the canned StubAgent even when Part 2's agent package is installed."""

    # ── Twilio ───────────────────────────────────────────────────────────────
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""

    # ── STT (Faster-Whisper) ─────────────────────────────────────────────────
    whisper_model_size: str = "large-v3"
    """Whisper model: tiny / base / small / medium / large-v3."""
    whisper_device: str = "auto"
    """'cuda', 'cpu', or 'auto' (auto-detects GPU)."""
    whisper_compute_type: str = "int8"
    """Quantisation: float16 (GPU) or int8 (CPU/GPU)."""
    whisper_beam_size: int = 1
    """Beam size 1 = fastest, lowest accuracy; increase for accuracy."""
    whisper_vad_filter: bool = True
    """Let Whisper apply its own internal VAD on top of Silero."""

    # ── VAD (Silero) ─────────────────────────────────────────────────────────
    vad_threshold: float = 0.5
    """Confidence threshold for speech vs silence (0.0–1.0)."""
    vad_min_speech_ms: int = 250
    """Minimum speech segment length in ms (shorter are discarded)."""
    vad_min_silence_ms: int = 600
    """Silence after speech that triggers end-of-utterance."""
    vad_sample_rate: int = 16000

    # ── TTS ──────────────────────────────────────────────────────────────────
    tts_engine: str = "piper"
    """Primary TTS: 'piper' (local) or 'edge' (cloud fallback)."""
    piper_binary: str = "piper"
    """Path to the piper binary (or 'piper' if on PATH)."""
    piper_voice_en: str = "en_US-amy-medium"
    """Piper voice model for English (filename without .onnx)."""
    piper_voice_hi: str = "hi_IN-hemant-medium"
    """Piper voice model for Hindi."""
    piper_models_dir: str = "models/piper"
    """Directory where .onnx voice model files are stored."""
    edge_voice_en: str = "en-IN-NeerjaNeural"
    """Edge-TTS voice for English."""
    edge_voice_hi: str = "hi-IN-SwaraNeural"
    """Edge-TTS voice for Hindi."""

    # ── Call pipeline ────────────────────────────────────────────────────────
    call_timeout_seconds: int = 300
    """Maximum call duration (5 min default). Call ends automatically after this."""
    silence_timeout_seconds: int = 30
    """Hang up if the caller is silent for this many seconds."""
    barge_in_enabled: bool = True
    """Stop TTS playback when caller starts speaking."""
    max_concurrent_calls: int = 10

    # ── Logging ──────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    recordings_dir: str = "recordings"
    """Directory to store call recordings (created if absent)."""
    enable_recordings: bool = False
    """Record calls (requires caller consent prompt)."""

    # ── HTTP server (Twilio webhook receiver) ────────────────────────────────
    server_host: str = "0.0.0.0"
    server_port: int = 8001
    public_url: str = ""
    """Public HTTPS URL the Twilio webhook will hit (e.g. ngrok URL)."""


_settings: TelephonySettings | None = None


def get_settings() -> TelephonySettings:
    global _settings
    if _settings is None:
        _settings = TelephonySettings()
    return _settings
