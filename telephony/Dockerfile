# Multi-stage Dockerfile for MedNexa Telephony (Twilio / STT / TTS Voice Pipeline)
FROM python:3.11-slim-bookworm AS builder

# Install system audio and compiler dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    libsndfile1 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /workspace

# Copy monorepo packages for local path resolution
COPY backend /workspace/backend
COPY agent /workspace/agent
COPY telephony /workspace/telephony

WORKDIR /workspace/telephony

# PyTorch flavour: "cpu" (default, ~2 GB smaller; matches MEDNEXA_TEL_WHISPER_DEVICE=cpu) or
# "auto" to pick the CUDA build for a GPU host:
#   docker compose build --build-arg TORCH_BACKEND=auto telephony
ARG TORCH_BACKEND=cpu

# Install packages into system site-packages
RUN uv pip install --system --no-cache --torch-backend=${TORCH_BACKEND} \
    -e /workspace/backend \
    -e /workspace/agent \
    -e /workspace/telephony

# Production runner image
FROM python:3.11-slim-bookworm AS runner

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    MEDNEXA_TEL_SERVER_HOST=0.0.0.0 \
    MEDNEXA_TEL_SERVER_PORT=8001

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /workspace/telephony /app
COPY --from=builder /workspace/agent /workspace/agent
COPY --from=builder /workspace/backend /workspace/backend

# Run as an unprivileged user. Its home holds the downloaded model caches (Whisper,
# Silero) and /app/recordings holds call recordings, so both must be writable.
RUN useradd --create-home --uid 1001 mednexa \
    && mkdir -p /app/recordings \
    && chown -R mednexa:mednexa /app
USER mednexa

EXPOSE 8001

HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["uvicorn", "telephony.main:app", "--host", "0.0.0.0", "--port", "8001"]
