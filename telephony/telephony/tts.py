from __future__ import annotations

import asyncio
import json
import re
import subprocess
from collections import OrderedDict
from collections.abc import AsyncIterator
from pathlib import Path

import numpy as np

from telephony.audio_codec import resample
from telephony.config import get_settings
from telephony.logging_setup import get_logger

log = get_logger("tts")

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2

PIPER_DEFAULT_RATE = 22050

WAV_HEADER_BYTES = 44

CHUNK_MS = 100
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_MS // 1000
CHUNK_BYTES = CHUNK_SAMPLES * SAMPLE_WIDTH


class PiperTTS:
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

    @staticmethod
    def _voice_sample_rate(voice: Path) -> int:
        config = voice.with_name(voice.name + ".json")
        try:
            return int(json.loads(config.read_text())["audio"]["sample_rate"])
        except (OSError, KeyError, ValueError, TypeError):
            log.warning("piper_sample_rate_unknown", config=str(config), assumed=PIPER_DEFAULT_RATE)
            return PIPER_DEFAULT_RATE

    def _is_available(self) -> bool:
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
        voice = self._voice_path(language)
        if not voice.exists():
            raise FileNotFoundError(f"Piper model not found: {voice}")

        cmd = [
            self._binary,
            "--model",
            str(voice),
            "--output-raw",
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
        return resample(raw_out, self._voice_sample_rate(voice), SAMPLE_RATE)

    async def async_synthesize(self, text: str, language: str = "en") -> AsyncIterator[bytes]:
        pcm = await self.synthesize(text, language)
        for i in range(0, len(pcm), CHUNK_BYTES):
            yield pcm[i : i + CHUNK_BYTES]


class EdgeTTS:
    def __init__(self) -> None:
        cfg = get_settings()
        self._voices: dict[str, str] = {
            "en": cfg.edge_voice_en,
            "hi": cfg.edge_voice_hi,
        }
        self._rate = cfg.edge_rate

    def _voice(self, language: str) -> str:
        return self._voices.get(language, self._voices["en"])

    async def synthesize(self, text: str, language: str = "en") -> bytes:
        import edge_tts  # type: ignore[import-untyped]

        communicate = edge_tts.Communicate(text, self._voice(language), rate=self._rate)
        mp3_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_chunks.append(chunk["data"])
        mp3_data = b"".join(mp3_chunks)
        if not mp3_data:
            return b""
        return await asyncio.to_thread(_decode_mp3, mp3_data)

    async def async_synthesize(self, text: str, language: str = "en") -> AsyncIterator[bytes]:
        pcm = await self.synthesize(text, language)
        for i in range(0, len(pcm), CHUNK_BYTES):
            yield pcm[i : i + CHUNK_BYTES]


def _decode_mp3(mp3: bytes) -> bytes:
    result = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
        input=mp3,
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg could not decode the audio: {result.stderr.decode()[:200]}")
    return result.stdout


def trim_silence(pcm: bytes, lead: float = 0.04, tail: float = 0.15) -> bytes:
    samples = np.frombuffer(pcm[: len(pcm) // 2 * 2], dtype=np.int16)
    if samples.size == 0:
        return pcm
    loud = np.flatnonzero(np.abs(samples.astype(np.int32)) > max(100, int(samples.max()) // 50))
    if loud.size == 0:
        return pcm
    start = max(0, int(loud[0]) - int(lead * SAMPLE_RATE))
    end = min(samples.size, int(loud[-1]) + int(tail * SAMPLE_RATE))
    return samples[start:end].tobytes()


async def _retry_pause(attempt: int) -> None:
    await asyncio.sleep(0.4 * (attempt + 1))


class TTSUnavailable(RuntimeError): ...


_SENTENCE_END = re.compile(r"(?<=[.!?।])\s+")

_ABBREVIATION = re.compile(r"(?:^|\s)(?:dr|mr|mrs|ms|prof|st|no|vs|a\.m|p\.m|[A-Za-z])\.$", re.I)


def split_sentences(text: str, min_chars: int = 30, max_parts: int = 4) -> list[str]:
    parts: list[str] = []
    for sentence in _SENTENCE_END.split(text.strip()):
        if not sentence:
            continue
        if parts and _ABBREVIATION.search(parts[-1]) or parts and len(parts[-1]) < min_chars:
            parts[-1] = f"{parts[-1]} {sentence}"
        else:
            parts.append(sentence)
    while len(parts) > 1 and (len(parts[-1]) < min_chars or len(parts) > max_parts):
        last = parts.pop()
        parts[-1] = f"{parts[-1]} {last}"
    return parts


class TTSEngine:
    _cache: OrderedDict[tuple[str, str], bytes] = OrderedDict()

    def __init__(self) -> None:
        cfg = get_settings()
        self._prefer_piper = cfg.tts_engine.lower() == "piper"
        self._retries = cfg.tts_retries
        self._timeout = cfg.tts_timeout_seconds
        self._cache_size = cfg.tts_cache_size
        self._piper = PiperTTS()
        self._edge = EdgeTTS()
        self._piper_ok: bool | None = None

    def _use_piper(self) -> bool:
        if not self._prefer_piper:
            return False
        if self._piper_ok is None:
            self._piper_ok = self._piper._is_available()
            if not self._piper_ok:
                log.warning("piper_not_found", fallback="edge-tts")
        return self._piper_ok

    async def _synthesize(self, text: str, language: str) -> bytes:
        try:
            if self._use_piper():
                log.debug("tts_piper", lang=language, chars=len(text))
                return await self._piper.synthesize(text, language)
        except Exception as exc:
            log.warning("piper_failed", error=str(exc), fallback="edge-tts")
            self._piper_ok = False
        log.debug("tts_edge", lang=language, chars=len(text))
        return await self._edge.synthesize(text, language)

    async def speak(self, text: str, language: str = "en") -> bytes:
        if not re.search(r"\w", text):
            return b""
        key = (language, text)
        if (cached := self._cache.get(key)) is not None:
            self._cache.move_to_end(key)
            return cached
        last: Exception | None = None
        for attempt in range(1 + self._retries):
            try:
                async with asyncio.timeout(self._timeout):
                    pcm = await self._synthesize(text, language)
            except Exception as exc:
                last = exc
                log.warning("tts_attempt_failed", attempt=attempt + 1, error=repr(exc)[:160])
                await _retry_pause(attempt)
                continue
            pcm = trim_silence(pcm)
            self._cache[key] = pcm
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
            return pcm
        raise TTSUnavailable(f"speech synthesis failed: {last!r}") from last

    async def stream(self, text: str, language: str = "en") -> AsyncIterator[bytes]:
        tasks = [asyncio.create_task(self.speak(p, language)) for p in split_sentences(text)]
        try:
            for task in tasks:
                pcm = await task
                for i in range(0, len(pcm), CHUNK_BYTES):
                    yield pcm[i : i + CHUNK_BYTES]
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def prewarm(self, phrases: dict[str, list[str]]) -> int:
        done = 0
        for language, texts in phrases.items():
            for text in texts:
                for sentence in split_sentences(text):
                    try:
                        await self.speak(sentence, language)
                        done += 1
                    except TTSUnavailable:
                        log.warning("tts_prewarm_failed", text=sentence[:40])
        return done
