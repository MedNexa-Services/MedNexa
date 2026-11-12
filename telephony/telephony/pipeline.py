from __future__ import annotations

import asyncio
import contextlib
import re
import time
from collections import deque
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from telephony.agent_interface import AgentInterface, create_agent
from telephony.api_client import BackendClient
from telephony.audio_utils import AudioProcessor, normalise_audio
from telephony.config import get_settings
from telephony.logging_setup import get_logger
from telephony.recording import CallRecorder
from telephony.stt import FasterWhisperSTT
from telephony.tts import TTSEngine
from telephony.vad import SileroVAD

log = get_logger("pipeline")

SendAudioFn = Callable[[bytes], Awaitable[None]]
ClearAudioFn = Callable[[], Awaitable[None]]
TransferFn = Callable[[], Awaitable[bool]]
EventFn = Callable[[dict[str, Any]], Awaitable[None]]

PCM_BYTES_PER_SECOND = 16000 * 2

PREROLL_BYTES = PCM_BYTES_PER_SECOND * 3 // 10

MIN_UTTERANCE_BYTES = PCM_BYTES_PER_SECOND * 3 // 10

MAX_UTTERANCE_BYTES = PCM_BYTES_PER_SECOND * 30

MAX_DRAIN_SECONDS = 20.0

_FAREWELL = re.compile(r"\bgood\s?-?bye\b|\bbye\b|अलविदा|धन्यवाद[\s,।!]*नमस्ते", re.IGNORECASE)

_NOISE_TRANSCRIPT = re.compile(
    r"^[\W_]*(you|uh+|um+|hmm+|mm+|ah+|thanks for watching!?|subtitles by .*)?[\W_]*$",
    re.IGNORECASE,
)

PHRASES: dict[str, dict[str, str]] = {
    "filler": {"en": "One moment, please.", "hi": "एक पल रुकिए।"},
    "repeat": {
        "en": "Sorry, I didn't catch that. Could you say it again?",
        "hi": "माफ़ कीजिए, मुझे समझ नहीं आया। कृपया दोबारा कहिए।",
    },
    "agent_failed": {
        "en": "Sorry, something went wrong on my side. Could you say that again?",
        "hi": "माफ़ कीजिए, मेरी तरफ़ से कुछ गड़बड़ हो गई। कृपया दोबारा कहिए।",
    },
    "still_there": {"en": "Are you still there?", "hi": "क्या आप अभी भी वहाँ हैं?"},
    "silent_goodbye": {
        "en": "I can't hear you, so I'll end the call now. Goodbye!",
        "hi": "मुझे आपकी आवाज़ नहीं आ रही, इसलिए मैं कॉल समाप्त कर रही हूँ। नमस्ते!",
    },
    "timeout": {
        "en": "I'm sorry, the call has exceeded the maximum duration. Goodbye!",
        "hi": "मुझे खेद है, कॉल की अधिकतम अवधि समाप्त हो गई है। नमस्ते!",
    },
    "no_transfer": {
        "en": "I'm sorry, I can't connect you to our staff on this line. "
        "Please call the hospital reception directly. Goodbye!",
        "hi": "माफ़ कीजिए, इस लाइन पर स्टाफ़ से जोड़ना संभव नहीं है। "
        "कृपया अस्पताल के रिसेप्शन पर सीधे कॉल करें। नमस्ते!",
    },
}


def fixed_phrases() -> dict[str, list[str]]:
    phrases = {lang: [p[lang] for p in PHRASES.values()] for lang in ("en", "hi")}
    try:
        from agent.agent import RETRY, TROUBLE  # type: ignore[import-not-found]
    except ImportError:
        return phrases
    for lang in phrases:
        phrases[lang] += [RETRY[lang], TROUBLE[lang]]
    return phrases


def _phrase(key: str, language: str) -> str:
    return PHRASES[key].get(language, PHRASES[key]["en"])


class CallPipeline:
    def __init__(
        self,
        session_id: str,
        caller_phone: str,
        send_audio: SendAudioFn,
        *,
        clear_audio: ClearAudioFn | None = None,
        transfer: TransferFn | None = None,
        agent: AgentInterface | None = None,
        language: str | None = None,
        on_event: EventFn | None = None,
    ) -> None:
        cfg = get_settings()
        self.session_id = session_id
        self.caller_phone = caller_phone
        self._send_audio = send_audio
        self._clear_audio = clear_audio
        self._transfer = transfer
        self._on_event = on_event
        self._cfg = cfg

        self._vad = SileroVAD()
        self._stt = FasterWhisperSTT()
        self._tts = TTSEngine()
        self._processor = AudioProcessor()
        self._agent: AgentInterface = agent or create_agent(caller_phone, cfg.hospital_id)
        self._api = BackendClient()
        self._recorder = CallRecorder(session_id)

        self._language: str = language or "en"
        self._language_chosen = language is not None
        if self._language_chosen and hasattr(self._agent, "fixed_language"):
            self._agent.fixed_language = self._language
        self._utterance_buf: bytearray = bytearray()
        self._preroll: deque[bytes] = deque()
        self._preroll_size = 0
        self._playback_until: float = 0.0
        self._barge_in_triggered = asyncio.Event()
        self._call_active = True
        self._busy = False
        self._ending: asyncio.Task[None] | None = None
        self._unheard = 0
        self._silence_prompted = False
        self._start_time: float = 0.0
        self._last_speech_time: float = 0.0

    async def run(self, audio_stream: AsyncIterator[bytes]) -> None:
        self._start_time = time.monotonic()
        self._last_speech_time = self._start_time

        with self._recorder:
            try:
                if self._recorder.enabled:
                    await self._speak(self._recorder.consent_prompt(self._language))
                    await self._log("ASSISTANT", self._recorder.consent_prompt(self._language))

                try:
                    greeting = await self._agent.get_greeting()
                except Exception:
                    log.exception("greeting_failed", session_id=self.session_id)
                    greeting = "Hello, thank you for calling. How can I help you today?"
                await self._speak(greeting)
                await self._log("ASSISTANT", greeting)

                try:
                    async with asyncio.timeout(self._cfg.call_timeout_seconds):
                        await self._process_stream(audio_stream)
                except TimeoutError:
                    log.warning("call_timeout", session_id=self.session_id)
                    await self._say("timeout")
            finally:
                await self._finish()

    async def _process_stream(self, audio_stream: AsyncIterator[bytes]) -> None:
        async for raw_chunk in audio_stream:
            if not self._call_active:
                break

            if await self._caller_went_quiet():
                break

            chunk = self._processor.process(raw_chunk)
            self._recorder.write(chunk)

            events = self._vad.process_chunk(chunk)
            speaking = "speech_start" in events or "speech" in events
            utterance_ends = "speech_end" in events

            if speaking:
                self._last_speech_time = time.monotonic()
                self._silence_prompted = False
                if self._cfg.barge_in_enabled and self._is_playing():
                    await self._interrupt_playback()

            if speaking or utterance_ends or self._vad.in_speech:
                if not self._utterance_buf:
                    self._utterance_buf.extend(b"".join(self._preroll))
                    self._preroll.clear()
                    self._preroll_size = 0
                self._utterance_buf.extend(chunk)
            else:
                self._preroll.append(chunk)
                self._preroll_size += len(chunk)
                while self._preroll_size > PREROLL_BYTES:
                    self._preroll_size -= len(self._preroll.popleft())

            if utterance_ends or len(self._utterance_buf) > MAX_UTTERANCE_BYTES:
                await self._process_utterance()

    async def _caller_went_quiet(self) -> bool:
        quiet_for = time.monotonic() - max(self._last_speech_time, self._playback_until)
        if quiet_for <= self._cfg.silence_timeout_seconds / 2:
            return False
        if not self._silence_prompted:
            log.info("silence_prompt", session_id=self.session_id)
            self._silence_prompted = True
            await self._say("still_there")
            return False
        log.info("silence_timeout", session_id=self.session_id)
        await self._say("silent_goodbye")
        self._call_active = False
        return True

    @property
    def listening(self) -> bool:
        return not self._busy

    async def _emit(self, event: dict[str, Any]) -> None:
        if self._on_event is not None:
            with contextlib.suppress(Exception):
                await self._on_event(event)

    async def _process_utterance(self) -> None:
        if not self._utterance_buf:
            return
        self._busy = True
        await self._emit({"state": "thinking"})
        try:
            await self._respond()
        except Exception:
            log.exception("turn_failed", session_id=self.session_id)
            await self._say("agent_failed")
        finally:
            self._busy = False
            await self._emit({"state": "listening"})

    async def _respond(self) -> None:
        pcm = bytes(self._utterance_buf)
        self._utterance_buf.clear()
        self._vad.reset()
        if len(pcm) < MIN_UTTERANCE_BYTES:
            return

        t0 = time.monotonic()
        pcm = normalise_audio(pcm)
        hint = self._language if self._language_chosen else None
        prompt = getattr(self._agent, "speech_hints", None)
        try:
            result = await asyncio.to_thread(
                self._stt.transcribe_bytes, pcm, language_hint=hint, prompt=prompt
            )
        except Exception:
            log.exception("stt_failed", session_id=self.session_id)
            await self._not_understood()
            return
        stt_ms = int((time.monotonic() - t0) * 1000)

        text = result.text.strip()
        if not text or _NOISE_TRANSCRIPT.match(text):
            log.info("utterance_ignored", session_id=self.session_id, text=text[:40])
            await self._not_understood()
            return
        self._unheard = 0

        if result.language != self._language:
            log.info(
                "language_switch",
                session_id=self.session_id,
                from_lang=self._language,
                to_lang=result.language,
            )
            self._language = result.language

        log.info(
            "utterance_transcribed",
            session_id=self.session_id,
            text=text[:80],
            lang=self._language,
            stt_ms=stt_ms,
        )
        await self._log("USER", text)

        self._last_speech_time = time.monotonic()
        t1 = time.monotonic()
        response = await self._ask_agent(text)
        agent_ms = int((time.monotonic() - t1) * 1000)

        log.info(
            "agent_responded",
            session_id=self.session_id,
            response=response[:80],
            agent_ms=agent_ms,
        )
        await self._log("ASSISTANT", response)
        await self._speak(response, language=self._language)
        self._last_speech_time = time.monotonic()
        self._silence_prompted = False

        if getattr(self._agent, "escalated", False):
            await self._hand_over()
        elif self._is_farewell(response):
            self._call_active = False

    async def _ask_agent(self, text: str) -> str:
        task = asyncio.create_task(self._agent.process(text, self._language))
        try:
            done, _ = await asyncio.wait({task}, timeout=self._cfg.thinking_filler_seconds)
            if not done:
                await self._say("filler", log_it=False)
            return await task
        except asyncio.CancelledError:
            task.cancel()
            raise
        except Exception:
            log.exception("agent_failed", session_id=self.session_id)
            return _phrase("agent_failed", self._language)

    async def _not_understood(self) -> None:
        self._unheard += 1
        if self._unheard >= 2:
            self._unheard = 0
            await self._say("repeat")

    async def _hand_over(self) -> None:
        self._call_active = False
        await asyncio.sleep(max(0.0, self._playback_until - time.monotonic()))
        if self._transfer is not None and await self._transfer():
            return
        await self._say("no_transfer")

    def _is_playing(self) -> bool:
        return time.monotonic() < self._playback_until

    async def _interrupt_playback(self) -> None:
        self._barge_in_triggered.set()
        self._playback_until = 0.0
        log.debug("barge_in", session_id=self.session_id)
        if self._clear_audio is not None:
            await self._clear_audio()

    async def _say(self, key: str, *, log_it: bool = True) -> None:
        text = _phrase(key, self._language)
        await self._speak(text)
        if log_it:
            await self._log("ASSISTANT", text)

    async def _speak(self, text: str, language: str | None = None) -> None:
        lang = language or self._language
        self._barge_in_triggered.clear()

        t0 = time.monotonic()
        try:
            async for chunk in self._tts.stream(text, lang):
                if self._barge_in_triggered.is_set():
                    log.debug("tts_interrupted", session_id=self.session_id)
                    break
                await self._send_audio(chunk)
                start = max(self._playback_until, time.monotonic())
                self._playback_until = start + len(chunk) / PCM_BYTES_PER_SECOND
        except Exception:
            log.exception("tts_failed", session_id=self.session_id)
            await self._emit({"speak": text})
        finally:
            tts_ms = int((time.monotonic() - t0) * 1000)
            log.debug("tts_done", tts_ms=tts_ms, lang=lang)

    async def _log(self, role: str, content: str) -> None:
        if role in ("USER", "ASSISTANT"):
            await self._emit({"transcript": {"role": role.lower(), "text": content}})
        await self._api.append_log(self.session_id, role, content)

    async def _finish(self) -> None:
        try:
            task = asyncio.current_task()
            if not (task and task.cancelling()):
                wait = min(self._playback_until - time.monotonic(), MAX_DRAIN_SECONDS)
                if wait > 0:
                    await asyncio.sleep(wait + 0.3)
        finally:
            self._ending = asyncio.create_task(self._end_call())
            await asyncio.shield(self._ending)

    async def _end_call(self) -> None:
        try:
            summary = await self._agent.get_summary()
        except Exception:
            log.exception("agent_summary_failed", session_id=self.session_id)
            summary = None
        await self._api.end_call(
            self.session_id,
            outcome=getattr(self._agent, "call_outcome", "OTHER"),
            summary=summary,
            language_detected=self._language,
            escalated_to_human=bool(getattr(self._agent, "escalated", False)),
        )
        await self._api.aclose()
        log.info("pipeline_done", session_id=self.session_id)

    @staticmethod
    def _is_farewell(text: str) -> bool:
        return bool(_FAREWELL.search(text))
