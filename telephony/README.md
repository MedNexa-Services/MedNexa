# MedNexa — Part 3: Voice/Telephony Pipeline

> **Owner: Team Member 3 (Voice/Telephony Engineer)**

This package implements the full audio pipeline connecting phone calls to the MedNexa AI agent:

```
Caller → Twilio WebSocket → VAD → STT → AI Agent (Part 2) → TTS → Caller
```

---

## Directory Structure

```
telephony/
├── telephony/
│   ├── config.py          # All settings (env-vars prefixed MEDNEXA_TEL_)
│   ├── logging_setup.py   # structlog JSON logging
│   ├── api_client.py      # HTTP client → Part 1 backend (call session CRUD)
│   ├── vad.py             # Silero VAD — speech/silence detection
│   ├── stt.py             # Faster-Whisper STT + language detection
│   ├── tts.py             # Piper TTS (local) + Edge-TTS (cloud fallback)
│   ├── audio_utils.py     # Noise suppression, gain normalisation
│   ├── recording.py       # Call recorder (WAV files + consent prompt)
│   ├── agent_interface.py # Protocol for Part 2's agent + StubAgent for dev
│   ├── pipeline.py        # CallPipeline — orchestrates the full call
│   ├── twilio_handler.py  # Twilio webhook + Media Streams WebSocket
│   └── main.py            # FastAPI app entry point
└── tests/
    ├── conftest.py
    ├── test_vad.py
    ├── test_stt.py
    ├── test_tts_and_audio.py
    └── test_pipeline.py
```

---

## Quick Start

### 1. Install dependencies

```bash
# Requires Python 3.11+
pip install uv
uv pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — fill in Twilio credentials, hospital UUID, Piper paths
```

### 3. Install Piper TTS (optional — Edge-TTS is the automatic fallback)

```bash
# Download binary from https://github.com/rhasspy/piper/releases
# Download voices from https://huggingface.co/rhasspy/piper-voices
mkdir -p models/piper
# Place en_US-amy-medium.onnx + .json in models/piper/
# Place hi_IN-hemant-medium.onnx + .json in models/piper/
```

### 4. Run the telephony server

```bash
uvicorn telephony.main:app --host 0.0.0.0 --port 8001 --reload
```

### 5. Expose to Twilio via ngrok

```bash
ngrok http 8001
# Copy the https URL and set MEDNEXA_TEL_PUBLIC_URL in .env
```

### 6. Configure Twilio

In your Twilio Console → Phone Number → Voice webhook:
- **URL**: `https://your-ngrok-url.ngrok.io/twilio/voice`
- **Method**: POST

---

## Architecture

### Call Flow

```
INCOMING CALL
     │
     ▼
Twilio PBX  ──webhook──▶  POST /twilio/voice
     │                        │
     │                    TwiML <Stream>
     │                        │
     ▼                        ▼
Twilio WS  ──μ-law──▶  WS /twilio/stream/{sid}
     ▲                        │
     │               decode μ-law → PCM 16kHz
     │                        │
     │               ┌────────▼────────┐
     │               │   SileroVAD     │  detect speech/silence
     │               └────────┬────────┘
     │                        │ utterance buffer
     │               ┌────────▼────────┐
     │               │ FasterWhisper   │  PCM → text + language
     │               └────────┬────────┘
     │                        │ TranscriptionResult
     │               ┌────────▼────────┐
     │               │  AI Agent       │  Part 2's MedNexaAgent
     │               └────────┬────────┘
     │                        │ response text
     │               ┌────────▼────────┐
     │               │  TTS Engine     │  Piper / Edge-TTS
     │               └────────┬────────┘
     │                        │ PCM 16kHz
     │               encode PCM → μ-law
     └────────────────────────┘
```

### Barge-in Detection

When TTS is playing and the VAD detects `speech_start`, a `barge_in_triggered`
event is set. The TTS streaming loop checks this flag between chunks and stops
immediately if set. This lets callers interrupt the AI mid-sentence.

### Language Detection

- Faster-Whisper reports the detected language on every transcription.
- Normalised to `"en"` or `"hi"` (any other language → English default).
- On a language switch, the TTS voice is also switched (Amy → Swara).

---

## Integration with Part 2 (AI Agent)

The pipeline creates one agent per call with `create_agent()`
(`telephony/agent_interface.py`): Part 2's `MedNexaAgent` when its package is
installed, otherwise the canned `StubAgent` (with a warning in the logs).

```bash
uv sync --extra agent     # installs ../agent (and the backend service layer it uses)
```

The agent reads the database directly, so the telephony process also needs
`MEDNEXA_DATABASE_URL` and the agent's `MEDNEXA_AGENT_*` model settings (see
`agent/.env.example`). Set `MEDNEXA_TEL_USE_STUB_AGENT=true` to force the stub.

When the call ends, the session is closed with the agent's `call_outcome` and
`escalated` flag (the stub reports `OTHER`).

Any agent implementing the `AgentInterface` protocol can be passed explicitly:
```python
async def get_greeting(self) -> str: ...
async def process(self, text: str, language: str) -> str: ...
async def get_summary(self) -> str | None: ...
```

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use monkeypatching — no real Torch/Whisper/Piper needed.

---

## Deliverables Checklist

| # | Task | Status |
|---|---|---|
| 3.1 | Twilio webhook (prototype telephony) | ✅ `twilio_handler.py` |
| 3.2 | WebSocket audio bridge | ✅ `twilio_handler.py` + `main.py` |
| 3.3 | Silero VAD | ✅ `vad.py` |
| 3.4 | Faster-Whisper STT | ✅ `stt.py` |
| 3.5 | Language detection (en/hi) | ✅ `stt.py` |
| 3.6 | Piper TTS (Hindi + English voices) | ✅ `tts.py` |
| 3.7 | Edge-TTS fallback | ✅ `tts.py` |
| 3.8 | Audio streaming to caller | ✅ `pipeline.py` |
| 3.9 | Barge-in detection | ✅ `pipeline.py` |
| 3.10 | Call session management (via Part 1 API) | ✅ `api_client.py` + `pipeline.py` |
| 3.11 | DTMF fallback | 🔜 Phase 2 (P2) |
| 3.12 | Noise suppression + gain control | ✅ `audio_utils.py` |
| 3.13 | Call recording + consent prompt | ✅ `recording.py` |
| 3.14 | Load testing | 🔜 Phase 2 |
