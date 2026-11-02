from __future__ import annotations

import wave
from datetime import UTC, datetime
from pathlib import Path

from telephony.config import get_settings
from telephony.logging_setup import get_logger

log = get_logger("recorder")

CONSENT_PROMPT_EN = (
    "Please note that this call is recorded for quality and training purposes. "
    "If you do not want to be recorded, you can end the call now."
)
CONSENT_PROMPT_HI = (
    "कृपया ध्यान दें कि गुणवत्ता और प्रशिक्षण के लिए यह कॉल रिकॉर्ड की जा रही है। "
    "यदि आप रिकॉर्डिंग नहीं चाहते, तो आप अभी कॉल समाप्त कर सकते हैं।"
)


class CallRecorder:
    def __init__(self, session_id: str) -> None:
        cfg = get_settings()
        self._enabled = cfg.enable_recordings
        self._session_id = session_id
        self._path: Path | None = None
        self._wav: wave.Wave_write | None = None

        if self._enabled:
            recordings_dir = Path(cfg.recordings_dir)
            recordings_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            self._path = recordings_dir / f"{session_id}_{ts}.wav"

    def __enter__(self) -> CallRecorder:
        if self._enabled and self._path:
            self._wav = wave.open(str(self._path), "wb")
            self._wav.setnchannels(1)
            self._wav.setsampwidth(2)
            self._wav.setframerate(16000)
            log.info("recording_started", path=str(self._path))
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def write(self, pcm: bytes) -> None:
        if self._wav is not None and pcm:
            self._wav.writeframes(pcm)

    def close(self) -> None:
        if self._wav is not None:
            self._wav.close()
            self._wav = None
            log.info("recording_saved", path=str(self._path))

    @property
    def path(self) -> Path | None:
        return self._path

    @property
    def enabled(self) -> bool:
        return self._enabled

    def consent_prompt(self, language: str = "en") -> str:
        return CONSENT_PROMPT_HI if language == "hi" else CONSENT_PROMPT_EN
