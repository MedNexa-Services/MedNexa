# MedNexa telephony

Connects phone calls to the AI receptionist:

```
Caller -> Twilio media stream -> VAD -> Whisper -> agent -> TTS -> Caller
```

The same pipeline also serves a test page at `/call`, where you can talk to the
receptionist from a browser without a phone line.

## Directory Structure

```
telephony/
├── telephony/
│   ├── config.py          # All settings (env-vars prefixed MEDNEXA_TEL_)
│   ├── logging_setup.py   # structlog JSON logging
│   ├── api_client.py      # backend calls: start, log and end a call
│   ├── vad.py             # Silero VAD, speech/silence detection
│   ├── stt.py             # Faster-Whisper STT + language detection
│   ├── tts.py             # Piper TTS (local) + Edge-TTS (cloud fallback)
│   ├── audio_utils.py     # Noise suppression, gain normalisation
│   ├── recording.py       # Call recorder (WAV files + consent prompt)
│   ├── agent_interface.py # what the pipeline needs from an agent; StubAgent
│   ├── pipeline.py        # CallPipeline, runs the full call
│   ├── twilio_handler.py  # Twilio webhook + Media Streams WebSocket
│   ├── call.html          # the /call test page
│   └── main.py            # FastAPI app: /health, /call, /ws/call, Twilio routes
└── tests/
    ├── conftest.py
    ├── test_vad.py
    ├── test_stt.py
    ├── test_tts_and_audio.py
    └── test_pipeline.py
```

## Running it

### 1. Install dependencies

```bash
# Requires Python 3.11+
pip install uv
uv pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Set the hospital id, and the Twilio credentials and Piper paths if you use them
```

### 3. Install Piper TTS (optional: without it the Edge voices are used)

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

### 5. Try a call

Open `http://localhost:8001/call` and start a call. For Twilio, expose the server over
HTTPS:

```bash
ngrok http 8001
# Copy the https URL and set MEDNEXA_TEL_PUBLIC_URL in .env
```

### 6. Configure Twilio

In the Twilio console, set the phone number's voice webhook to:
- **URL**: `https://your-ngrok-url.ngrok.io/twilio/voice`
- **Method**: POST

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
     │               │  AI Agent       │  agent.MedNexaAgent
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

If the caller starts talking while a reply is playing, the reply stops and Twilio drops
the audio it has queued, so callers can interrupt the receptionist. The /call page
instead mutes the microphone while the receptionist speaks, because a laptop's
microphone would otherwise hear the speakers.

While a reply is being worked out, incoming audio is dropped, so background noise isn't
taken as the caller's next turn. Transcripts that are empty, low-confidence or a typical
Whisper noise word ("you", "hmm") are ignored instead of answered.

### Language Detection

Whisper detects the language of every utterance; the reply is spoken in the same
language. The /call page fixes the call to English instead.

## Keeping a call alive

A call only ends when the caller hangs up, the agent says goodbye, or its time runs out
(10 minutes). Everything else is survived:

- **Model errors:** retried; the caller is asked to repeat; only the third failed turn in a
  row goes to staff (see the agent README).
- **Voice errors:** each sentence is retried, and sentences already made are remembered, so
  fixed phrases such as "One moment, please" still play if the voice service can't be reached.
  If no audio can be made, the call goes on and the /call page speaks the reply with the
  browser's own voice.
- **Speech recognition errors** and noise: ignored; two utterances in a row with no words get
  "Sorry, I didn't catch that".
- **Slow replies:** "One moment, please" after 4 seconds (`THINKING_FILLER_SECONDS`).
- **Silence:** "Are you still there?" after 15 seconds, goodbye after 15 more, counted from the
  end of the last reply.
- **The last words** finish playing before the line closes.
- **Busy line:** over `MAX_CONCURRENT_CALLS` (10), callers are told to try again.
- Calls that are cut off anyway are closed by the backend after 30 minutes.

## Speech and voice

Whisper (`base`, beam size 5) is given the hospital's doctor and department names as a
prompt, which raised accuracy on a 100-clip test from 93.0% to 96.2%; the `small` model is
slightly better but 3.6 times slower. The 0.3 s before speech is detected is kept, so the
first syllable isn't lost.

The voice is made a sentence at a time, in parallel, so a long reply starts after its first
sentence. The silence the voice service puts around each sentence (about a second) is
trimmed, and the speed is `EDGE_RATE` (default `+5%`). Text is converted with `ffmpeg`.

The /call page shows what the receptionist heard and said as it happens.

## The agent

The pipeline creates one agent per call with `create_agent()`
(`telephony/agent_interface.py`): `MedNexaAgent` when its package is
installed, otherwise the canned `StubAgent` (with a warning in the logs).

```bash
uv sync --extra agent     # installs ../agent (and the backend service layer it uses)
```

The agent reads the database directly, so the telephony process also needs
`MEDNEXA_DATABASE_URL` and the agent's `MEDNEXA_AGENT_*` model settings (see
`agent/.env.example`). Set `MEDNEXA_TEL_USE_STUB_AGENT=true` to force the stub.

When the call ends, the session is closed with the agent's `call_outcome` and
`escalated` flag (the stub reports `OTHER`).

When the agent hands a call over to a person, the AI stops and, on Twilio calls, the
call is connected to `MEDNEXA_TEL_TRANSFER_PHONE_NUMBER` once the caller has heard
"please stay on the line". Without that number (or on the local WebSocket), the caller
is asked to call reception directly.

Any agent implementing the `AgentInterface` protocol can be passed explicitly:
```python
async def get_greeting(self) -> str: ...
async def process(self, text: str, language: str) -> str: ...
async def get_summary(self) -> str | None: ...
```

## Tests

```bash
pytest tests/ -v
```

Tests use monkeypatching, so no real Torch/Whisper/Piper needed.

