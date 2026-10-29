"""CallPipeline — orchestrates a single phone call end-to-end.

Flow per utterance:
  audio_stream → VAD → accumulate utterance → STT → Agent → TTS → play back

Key responsibilities:
  3.2  Audio stream handler
  3.3  VAD integration (Silero VAD)
  3.4  Faster-Whisper STT
  3.5  Language detection from STT output
  3.6  Piper/Edge TTS
  3.8  Audio streaming back to caller
  3.9  Barge-in detection (stop TTS when caller speaks)
  3.10 Call session management (start, end, timeout)
  3.12 Audio quality optimisation (via AudioProcessor)
  3.13 Call recording

Usage (Twilio MediaStreams WebSocket)::

    pipeline = CallPipeline(session_id, caller_phone, send_audio_fn)
    await pipeline.run(audio_byte_iterator)

``send_audio_fn`` is an async callable that sends a raw PCM chunk to the
caller's audio stream (Twilio / Asterisk bridge provides this).
"""

from __future__ import annotations

import asyncio
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable

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

# Pipeline audio: 16 kHz mono int16 -> 32000 bytes per second of playback.
PCM_BYTES_PER_SECOND = 16000 * 2

# Closing phrases (Part 2's agent says these only in its final reply).
_FAREWELL = re.compile(r"\bgood\s?-?bye\b|\bbye\b|अलविदा|धन्यवाद[\s,।!]*नमस्ते", re.IGNORECASE)

# Maximum buffer for one utterance (prevents runaway memory if VAD misses end)
MAX_UTTERANCE_BYTES = 16000 * 2 * 30  # 30 seconds of 16 kHz int16


class CallPipeline:
    """Manages the full lifetime of a single inbound call.

    Parameters
    ----------
    session_id:
        UUID of the ``CallSession`` row already created via Part 1's API.
    caller_phone:
        E.164 phone number of the caller (e.g. "+919876543210").
    send_audio:
        Async function that sends a raw PCM chunk to the caller.
    clear_audio:
        Optional async function that discards audio already queued on the
        caller's side (Twilio's "clear"), used when the caller barges in.
    agent:
        MedNexaAgent or StubAgent instance.
    """

    def __init__(
        self,
        session_id: str,
        caller_phone: str,
        send_audio: SendAudioFn,
        *,
        clear_audio: ClearAudioFn | None = None,
        agent: AgentInterface | None = None,
    ) -> None:
        cfg = get_settings()
        self.session_id = session_id
        self.caller_phone = caller_phone
        self._send_audio = send_audio
        self._clear_audio = clear_audio
        self._cfg = cfg

        # Core components
        self._vad = SileroVAD()
        self._stt = FasterWhisperSTT()
        self._tts = TTSEngine()
        self._processor = AudioProcessor()
        self._agent: AgentInterface = agent or create_agent(caller_phone, cfg.hospital_id)
        self._api = BackendClient()
        self._recorder = CallRecorder(session_id)

        # State
        self._language: str = "en"
        self._utterance_buf: bytearray = bytearray()
        # Audio is sent faster than real time and buffered by the telephony side,
        # so "playing" lasts until the caller has actually heard it all.
        self._playback_until: float = 0.0
        self._barge_in_triggered = asyncio.Event()
        self._call_active = True
        self._start_time: float = 0.0
        self._last_speech_time: float = 0.0

    # ── public entry point ────────────────────────────────────────────────────

    async def run(self, audio_stream: AsyncIterator[bytes]) -> None:
        """Drive the call from audio input to audio output.

        This coroutine returns when the call ends (caller hangs up,
        timeout, or the agent says goodbye).
        """
        self._start_time = time.monotonic()
        self._last_speech_time = self._start_time

        with self._recorder:
            # Play consent prompt if recording is enabled
            if self._recorder.enabled:
                await self._speak(self._recorder.consent_prompt(self._language))
                await self._log("ASSISTANT", self._recorder.consent_prompt(self._language))

            # Play opening greeting
            greeting = await self._agent.get_greeting()
            await self._speak(greeting)
            await self._log("ASSISTANT", greeting)

            try:
                async with asyncio.timeout(self._cfg.call_timeout_seconds):
                    await self._process_stream(audio_stream)
            except TimeoutError:
                log.warning("call_timeout", session_id=self.session_id)
                timeout_msg = (
                    "I'm sorry, the call has exceeded the maximum duration. Goodbye!"
                    if self._language == "en"
                    else "मुझे खेद है, कॉल की अधिकतम अवधि समाप्त हो गई है। नमस्ते!"
                )
                await self._speak(timeout_msg)
            finally:
                await self._end_call()

    # ── stream processing ─────────────────────────────────────────────────────

    async def _process_stream(self, audio_stream: AsyncIterator[bytes]) -> None:
        """Main loop: read audio chunks, run VAD, accumulate utterances, transcribe."""
        async for raw_chunk in audio_stream:
            if not self._call_active:
                break

            # Check silence timeout
            elapsed_silence = time.monotonic() - self._last_speech_time
            if elapsed_silence > self._cfg.silence_timeout_seconds:
                log.info("silence_timeout", session_id=self.session_id)
                silence_msg = (
                    "Are you still there? Goodbye!"
                    if self._language == "en"
                    else "क्या आप अभी भी वहाँ हैं? नमस्ते!"
                )
                await self._speak(silence_msg)
                break

            # Optionally apply noise suppression to inbound audio
            chunk = self._processor.process(raw_chunk)

            # Write to recording (inbound side)
            self._recorder.write(chunk)

            # Run VAD
            events = self._vad.process_chunk(chunk)
            speaking = "speech_start" in events or "speech" in events
            utterance_ends = "speech_end" in events

            if speaking:
                self._last_speech_time = time.monotonic()

                # Barge-in: interrupt TTS if the caller is still hearing it
                if self._cfg.barge_in_enabled and self._is_playing():
                    await self._interrupt_playback()

            # Keep each chunk once while an utterance is open. VAD works in 32 ms
            # frames, so a short chunk can carry no event at all mid-utterance,
            # and a long one can carry several.
            if speaking or utterance_ends or self._vad.in_speech:
                self._utterance_buf.extend(chunk)

            if utterance_ends or len(self._utterance_buf) > MAX_UTTERANCE_BYTES:
                # (the size check is a safety valve against runaway memory)
                await self._process_utterance()

    # ── utterance handling ────────────────────────────────────────────────────

    async def _process_utterance(self) -> None:
        """Transcribe the buffered utterance, call the agent, speak the response."""
        if not self._utterance_buf:
            return

        pcm = bytes(self._utterance_buf)
        self._utterance_buf.clear()
        self._vad.reset()

        # STT
        t0 = time.monotonic()
        # Level the whole utterance (not per chunk) so quiet lines transcribe well.
        pcm = normalise_audio(pcm)

        # Whisper is blocking: run it off the event loop so other calls keep flowing.
        # No language hint, so each utterance's language is detected afresh.
        result = await asyncio.to_thread(self._stt.transcribe_bytes, pcm)
        stt_ms = int((time.monotonic() - t0) * 1000)

        # Update detected language
        if result.language != self._language:
            log.info(
                "language_switch",
                session_id=self.session_id,
                from_lang=self._language,
                to_lang=result.language,
            )
            self._language = result.language

        text = result.text.strip()
        log.info(
            "utterance_transcribed",
            session_id=self.session_id,
            text=text[:80],
            lang=self._language,
            stt_ms=stt_ms,
        )

        if not text:
            # Empty transcription — ask them to repeat
            repeat_prompt = (
                "I'm sorry, I didn't catch that. Could you please repeat?"
                if self._language == "en"
                else "माफ करें, मुझे समझ नहीं आया। कृपया दोबारा कहें।"
            )
            await self._speak(repeat_prompt)
            return

        # Log the caller's turn
        await self._log("USER", text)

        # Agent
        t1 = time.monotonic()
        response = await self._agent.process(text, self._language)
        agent_ms = int((time.monotonic() - t1) * 1000)

        log.info(
            "agent_responded",
            session_id=self.session_id,
            response=response[:80],
            agent_ms=agent_ms,
        )

        # Log the agent's turn
        await self._log("ASSISTANT", response)

        # TTS
        await self._speak(response, language=self._language)

        # Detect "goodbye" intent to end the call cleanly
        if self._is_farewell(response):
            self._call_active = False

    # ── TTS playback ──────────────────────────────────────────────────────────

    def _is_playing(self) -> bool:
        return time.monotonic() < self._playback_until

    async def _interrupt_playback(self) -> None:
        """Stop the current reply: no more chunks, and drop what is already queued."""
        self._barge_in_triggered.set()
        self._playback_until = 0.0
        log.debug("barge_in", session_id=self.session_id)
        if self._clear_audio is not None:
            await self._clear_audio()

    async def _speak(self, text: str, language: str | None = None) -> None:
        """Synthesise text and stream audio to the caller."""
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
        finally:
            tts_ms = int((time.monotonic() - t0) * 1000)
            log.debug("tts_done", tts_ms=tts_ms, lang=lang)

    # ── logging ───────────────────────────────────────────────────────────────

    async def _log(self, role: str, content: str) -> None:
        """Append a turn to the call log (non-blocking, errors are swallowed)."""
        await self._api.append_log(self.session_id, role, content)

    # ── call lifecycle ────────────────────────────────────────────────────────

    async def _end_call(self) -> None:
        """Finalise session in the backend and clean up resources."""
        try:
            summary = await self._agent.get_summary()
        except Exception:
            log.exception("agent_summary_failed", session_id=self.session_id)
            summary = None
        # Part 2's agent reports a backend CallOutcome and whether it handed the
        # caller to staff; other agents (e.g. the stub) fall back to OTHER.
        await self._api.end_call(
            self.session_id,
            outcome=getattr(self._agent, "call_outcome", "OTHER"),
            summary=summary,
            language_detected=self._language,
            escalated_to_human=bool(getattr(self._agent, "escalated", False)),
        )
        await self._api.aclose()
        log.info("pipeline_done", session_id=self.session_id)

    # ── helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _is_farewell(text: str) -> bool:
        """Did the agent close the call? Only explicit closing phrases count: words
        like "धन्यवाद" (thank you) or "take care" also occur mid-conversation."""
        return bool(_FAREWELL.search(text))
