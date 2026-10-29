"""Text-to-Speech engines: Piper (local, primary) and Edge-TTS (cloud, fallback).

Architecture:
  - ``PiperTTS``: calls the `piper` CLI binary and streams WAVE audio.
  - ``EdgeTTS``: uses the ``edge-tts`` Python library (free Microsoft cloud).
  - ``TTSEngine``: unified interface that tries Piper first, falls back to Edge.

Both engines expose an ``async_synthesize`` method that yields raw PCM audio
chunks (16-bit, mono, 16 kHz) suitable for direct playback to the caller.

Piper setup:
  Download the binary from https://github.com/rhasspy/piper/releases and
  put it in your PATH (or set ``MEDNEXA_TEL_PIPER_BINARY``).
  Download voice models (.onnx + .json) from Hugging Face and put them in
  the directory set by ``MEDNEXA_TEL_PIPER_MODELS_DIR``.
"""

from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import AsyncIterator

from telephony.config import get_settings
from telephony.logging_setup import get_logger
import struct

_ULAW_TABLE: list[int] = []


def _build_ulaw_table() -> None:
    """Pre-compute the μ-law to linear int16 lookup table (ITU-T G.711)."""
    global _ULAW_TABLE
    _ULAW_TABLE = []
    for i in range(256):
        ulaw = ~i & 0xFF
        sign = ulaw & 0x80
        exponent = (ulaw >> 4) & 0x07
        mantissa = ulaw & 0x0F
        sample = ((mantissa << 3) + 0x84) << exponent
        sample -= 0x84
        if sign:
            sample = -sample
        _ULAW_TABLE.append(sample)


_build_ulaw_table()


def ulaw_to_linear(data: bytes) -> bytes:
    """Decode G.711 μ-law bytes to 16-bit signed PCM (little-endian)."""
    return struct.pack(f"<{len(data)}h", *(_ULAW_TABLE[b] for b in data))


def upsample_8k_to_16k(pcm_8k: bytes) -> bytes:
    """Simple 2x linear upsampler: 8 kHz → 16 kHz."""
    samples = struct.unpack(f"<{len(pcm_8k) // 2}h", pcm_8k)
    upsampled = []
    for s in samples:
        upsampled.extend([s, s])
    return struct.pack(f"<{len(upsampled)}h", *upsampled)


def pcm_16k_to_ulaw_8k(pcm_16k: bytes) -> bytes:
    """Convert 16 kHz int16 PCM to 8 kHz μ-law for Twilio playback."""
    samples = struct.unpack(f"<{len(pcm_16k) // 2}h", pcm_16k)
    downsampled = samples[::2]

    ulaw_bytes = []
    for sample in downsampled:
        sign = 0
        if sample < 0:
            sample = -sample
            sign = 0x80
        sample = min(sample, 32767)
        sample += 0x84
        exp = 7
        for exp in range(7, 0, -1):
            if sample >= (1 << (exp + 3)):
                break
        mantissa = (sample >> (exp + 3)) & 0x0F
        ulaw = ~(sign | (exp << 4) | mantissa) & 0xFF
        ulaw_bytes.append(ulaw)
    return bytes(ulaw_bytes)


log = get_logger("tts")

# Output audio spec (must match what Asterisk/Twilio expects)
SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # bytes, int16

# WAV header is 44 bytes; we strip it and send raw PCM downstream.
WAV_HEADER_BYTES = 44

# How large each yielded chunk is (100 ms of audio)
CHUNK_MS = 100
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_MS // 1000  # 1600 samples
CHUNK_BYTES = CHUNK_SAMPLES * SAMPLE_WIDTH       # 3200 bytes


# ── Piper TTS ─────────────────────────────────────────────────────────────────


class PiperTTS:
    """Local TTS using the Piper binary.

    Generates audio by running the piper binary as a subprocess and capturing
    its stdout (raw WAV). The WAV header is stripped and raw PCM is returned.
    """

    def __init__(self) -> None:
        cfg = get_settings()
        self._binary = cfg.piper_binary
        self._models_dir = Path(cfg.piper_models_dir)
        self._voices: dict[str, str] = {
            "en": cfg.piper_voice_en,
            "hi": cfg.piper_voice_hi,
        }

    def _voice_path(self, language: str) -> Path:
        voice_name = self._voices.get(language, self._voices["en"])
        return self._models_dir / f"{voice_name}.onnx"

    def _is_available(self) -> bool:
        """Check if the piper binary exists and a model file is present."""
        try:
            result = subprocess.run(
                [self._binary, "--version"],
                capture_output=True,
                timeout=3,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        """Synthesize text and return raw PCM bytes (blocking subprocess)."""
        voice = self._voice_path(language)
        if not voice.exists():
            raise FileNotFoundError(f"Piper model not found: {voice}")

        cmd = [
            self._binary,
            "--model", str(voice),
            "--output-raw",   # raw PCM output
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        raw_out, raw_err = await proc.communicate(input=text.encode("utf-8"))
        if proc.returncode != 0:
            raise RuntimeError(f"Piper failed: {raw_err.decode()}")
        # piper --output-raw produces raw s16le PCM (no header)
        return raw_out

    async def async_synthesize(
        self, text: str, language: str = "en"
    ) -> AsyncIterator[bytes]:
        """Stream raw PCM chunks from Piper."""
        pcm = await self.synthesize(text, language)
        for i in range(0, len(pcm), CHUNK_BYTES):
            yield pcm[i : i + CHUNK_BYTES]


# ── Edge-TTS ──────────────────────────────────────────────────────────────────


class EdgeTTS:
    """Cloud TTS using Microsoft Edge's free neural voices.

    Outputs MP3 which is converted to raw PCM via pydub/ffmpeg.
    Requires ffmpeg to be installed (or pydub's AudioSegment will fail).
    """

    def __init__(self) -> None:
        cfg = get_settings()
        self._voices: dict[str, str] = {
            "en": cfg.edge_voice_en,
            "hi": cfg.edge_voice_hi,
        }

    def _voice(self, language: str) -> str:
        return self._voices.get(language, self._voices["en"])

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        """Synthesize text via Edge-TTS and return raw PCM bytes."""
        import edge_tts  # type: ignore[import-untyped]
        from pydub import AudioSegment  # type: ignore[import-untyped]

        voice = self._voice(language)
        communicate = edge_tts.Communicate(text, voice)

        # Collect all audio chunks from Edge-TTS
        mp3_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_chunks.append(chunk["data"])
        mp3_data = b"".join(mp3_chunks)

        if not mp3_data:
            return b""

        # Convert MP3 → 16 kHz mono int16 PCM using pydub
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(mp3_data)
            tmp_path = f.name

        audio = AudioSegment.from_mp3(tmp_path)
        audio = audio.set_frame_rate(SAMPLE_RATE).set_channels(CHANNELS).set_sample_width(SAMPLE_WIDTH)
        Path(tmp_path).unlink(missing_ok=True)
        return audio.raw_data  # type: ignore[return-value]

    async def async_synthesize(
        self, text: str, language: str = "en"
    ) -> AsyncIterator[bytes]:
        """Stream raw PCM chunks from Edge-TTS."""
        pcm = await self.synthesize(text, language)
        for i in range(0, len(pcm), CHUNK_BYTES):
            yield pcm[i : i + CHUNK_BYTES]


# ── Unified engine ────────────────────────────────────────────────────────────


class TTSEngine:
    """Unified TTS facade: tries Piper first, falls back to Edge-TTS.

    On first call, piper availability is checked once and remembered.
    If piper is not available or fails, Edge-TTS is used automatically.
    """

    def __init__(self) -> None:
        cfg = get_settings()
        self._prefer_piper = cfg.tts_engine.lower() == "piper"
        self._piper = PiperTTS()
        self._edge = EdgeTTS()
        self._piper_ok: bool | None = None  # None = not yet checked

    def _use_piper(self) -> bool:
        if not self._prefer_piper:
            return False
        if self._piper_ok is None:
            self._piper_ok = self._piper._is_available()
            if not self._piper_ok:
                log.warning("piper_not_found", fallback="edge-tts")
        return self._piper_ok

    async def speak(self, text: str, language: str = "en") -> bytes:
        """Return raw PCM for the given text. Uses Piper or Edge-TTS."""
        if not text.strip():
            return b""
        try:
            if self._use_piper():
                log.debug("tts_piper", lang=language, chars=len(text))
                return await self._piper.synthesize(text, language)
        except Exception as exc:
            log.warning("piper_failed", error=str(exc), fallback="edge-tts")
            self._piper_ok = False

        log.debug("tts_edge", lang=language, chars=len(text))
        return await self._edge.synthesize(text, language)

    async def stream(
        self, text: str, language: str = "en"
    ) -> AsyncIterator[bytes]:
        """Yield raw PCM chunks as they become available."""
        pcm = await self.speak(text, language)
        for i in range(0, len(pcm), CHUNK_BYTES):
            yield pcm[i : i + CHUNK_BYTES]
