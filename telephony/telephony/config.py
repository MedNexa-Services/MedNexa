from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class TelephonySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEDNEXA_TEL_",
        env_file=".env",
        extra="ignore",
    )

    backend_url: str = "http://localhost:8000"
    """Backend URL, without a trailing slash."""

    backend_api_key: str = ""
    """Service key for the backend's /calls routes (the backend's MEDNEXA_SERVICE_API_KEY).
    Without it the backend rejects call-log requests with 401 once auth is enabled."""

    hospital_id: str = ""
    """The hospital whose calls this service answers."""

    use_stub_agent: bool = False
    """Answer with the canned StubAgent instead of the real agent."""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    transfer_phone_number: str = ""
    """Staff number (E.164) that calls are connected to when the agent hands over to a
    person. Empty = the caller is asked to call reception instead."""

    whisper_model_size: str = "large-v3"
    """Whisper model: tiny / base / small / medium / large-v3."""
    whisper_device: str = "auto"
    """'cuda', 'cpu', or 'auto' (auto-detects GPU)."""
    whisper_compute_type: str = "int8"
    """Quantisation: float16 (GPU) or int8 (CPU/GPU)."""
    whisper_beam_size: int = 5
    """Beam size 1 = fastest, lowest accuracy; 5 is a little slower and more accurate."""
    whisper_vad_filter: bool = True
    """Let Whisper apply its own internal VAD on top of Silero."""

    vad_threshold: float = 0.5
    """Confidence threshold for speech vs silence (0.0–1.0)."""
    vad_min_speech_ms: int = 250
    """Minimum speech segment length in ms (shorter are discarded)."""
    vad_min_silence_ms: int = 1000
    """Silence after speech that triggers end-of-utterance (shorter cuts callers off
    when they pause mid-sentence, e.g. while giving their age)."""
    vad_sample_rate: int = 16000

    tts_engine: str = "piper"
    """Primary TTS: 'piper' (local) or 'edge' (cloud fallback)."""
    piper_binary: str = "piper"
    """Path to the piper binary (or 'piper' if on PATH)."""
    piper_voice_en: str = "en_US-amy-medium"
    """Piper voice model for English (filename without .onnx)."""
    piper_voice_hi: str = "hi_IN-hemant-medium"
    piper_models_dir: str = "models/piper"
    """Directory where .onnx voice model files are stored."""
    edge_rate: str = "+5%"
    """Speaking speed of the Edge voices relative to normal, e.g. "+10%" or "-5%"."""
    tts_retries: int = 2
    """Extra tries when the voice service can't be reached."""
    tts_timeout_seconds: float = 10.0
    """Give up on one try of one sentence after this long."""
    tts_cache_size: int = 128
    """Sentences kept for reuse."""
    edge_voice_en: str = "en-IN-NeerjaNeural"
    edge_voice_hi: str = "hi-IN-SwaraNeural"

    call_timeout_seconds: int = 600
    """Longest a call can last (10 min default); it ends automatically after this."""
    silence_timeout_seconds: int = 30
    """Ask "are you still there?" after half of this many seconds of silence, and hang up
    after the other half. Counted from the end of the last reply."""
    thinking_filler_seconds: float = 4.0
    """Say "one moment, please" if the agent takes longer than this to answer."""
    barge_in_enabled: bool = True
    max_concurrent_calls: int = 10
    web_call_enabled: bool = True
    """The /call test page and /ws/call. They have no sign-in: anyone who can reach this
    port could start calls and use the AI model, so turn them off on a public server."""

    log_level: str = "INFO"
    recordings_dir: str = "recordings"
    """Directory to store call recordings (created if absent)."""
    enable_recordings: bool = False
    """Record calls (requires caller consent prompt)."""

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
