#!/usr/bin/env bash
# One-command setup for MedNexa: configures it, downloads the local language model,
# starts every service and loads a demo hospital.
#
#   ./setup.sh
#
# Needs Docker with Compose v2. On Windows run it from WSL 2 or Git Bash.
# Safe to run again: it keeps your existing .env and only fills in what is missing.

set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

MODEL="llama3.1:8b"
USE_GPU="auto"
PULL_MODEL=1
SEED_DEMO=1
START_STACK=1
STEP="starting"

usage() {
  cat <<'EOF'
Usage: ./setup.sh [options]

Sets up and starts MedNexa. Run it once and everything is in place.

Options:
  --model NAME   local model to download (default: llama3.1:8b)
  --cpu          do not use an NVIDIA GPU even if one is found
  --no-model     do not download the local language model
  --no-seed      do not load the demo hospital, doctors and bookings
  --no-start     prepare .env only, do not start the services
  -h, --help     show this help
EOF
}

if [ -t 1 ]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; RESET=$'\033[0m'
else
  BOLD=""; DIM=""; GREEN=""; YELLOW=""; RED=""; RESET=""
fi

step() { STEP="$1"; printf '\n%s==> %s%s\n' "$BOLD" "$1" "$RESET"; }
info() { printf '    %s\n' "$1"; }
warn() { printf '%s    Note: %s%s\n' "$YELLOW" "$1" "$RESET"; }
fail() { printf '\n%sError: %s%s\n' "$RED" "$1" "$RESET" >&2; exit 1; }

on_error() {
  printf '\n%sSetup stopped during: %s%s\n' "$RED" "$STEP" "$RESET" >&2
  printf 'Fix the problem above and run ./setup.sh again. It picks up where it left off.\n' >&2
}

random_hex() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "$1"
  else
    head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'
  fi
}

get_env() {
  grep -E "^$1=" .env | head -n 1 | cut -d= -f2- || true
}

set_env() {
  local tmp
  tmp="$(mktemp)"
  awk -v key="$1" -v value="$2" '
    BEGIN { FS = OFS = "=" }
    $1 == key { print key "=" value; found = 1; next }
    { print }
    END { if (!found) print key "=" value }
  ' .env > "$tmp"
  cat "$tmp" > .env
  rm -f "$tmp"
}

fill_if_empty() {
  if [ -z "$(get_env "$1")" ]; then
    set_env "$1" "$2"
    return 0
  fi
  return 1
}

wait_healthy() {
  local container="$1" seconds="$2" waited=0 status
  while [ "$waited" -lt "$seconds" ]; do
    status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container" 2>/dev/null || echo missing)"
    case "$status" in
      healthy|running) return 0 ;;
      exited|dead) fail "$container stopped. See the reason with: docker compose logs $container" ;;
    esac
    sleep 5
    waited=$((waited + 5))
    printf '.'
  done
  printf '\n'
  fail "$container did not become ready in $((seconds / 60)) minutes. See: docker compose logs $container"
}

check_docker() {
  step "Checking Docker"
  command -v docker >/dev/null 2>&1 ||
    fail "Docker is not installed. Install Docker Desktop from https://docs.docker.com/get-docker/ and run ./setup.sh again."
  docker compose version >/dev/null 2>&1 ||
    fail "Docker Compose v2 is missing. Update Docker Desktop, or install the compose plugin."
  docker info >/dev/null 2>&1 ||
    fail "Docker is installed but not running. Start Docker Desktop, wait until it says it is running, then run ./setup.sh again."
  [ -f docker-compose.yml ] && [ -f .env.example ] ||
    fail "Run this from the MedNexa folder (docker-compose.yml and .env.example were not found)."
  info "Docker $(docker version -f '{{.Server.Version}}' 2>/dev/null || echo ok) is ready."
}

prepare_env() {
  step "Preparing the configuration (.env)"
  local created_password=""
  if [ ! -f .env ]; then
    cp .env.example .env
    info "Created .env from .env.example."
  else
    info "Keeping your existing .env and filling in only what is missing."
  fi

  fill_if_empty POSTGRES_PASSWORD "$(random_hex 16)" && info "Generated a database password." || true
  fill_if_empty MEDNEXA_JWT_SECRET "$(random_hex 32)" && info "Generated the login signing secret." || true
  fill_if_empty MEDNEXA_SERVICE_API_KEY "$(random_hex 32)" && info "Generated the telephony service key." || true
  fill_if_empty MEDNEXA_ADMIN_EMAIL "${ADMIN_EMAIL:-admin@example.com}" || true
  if fill_if_empty MEDNEXA_ADMIN_PASSWORD "${ADMIN_PASSWORD:-$(random_hex 8)}"; then
    created_password="yes"
  fi
  fill_if_empty MEDNEXA_TEL_TTS_ENGINE "edge" || true
  set_env MEDNEXA_AGENT_LOCAL_MODEL "$MODEL"
  [ -n "$created_password" ] && info "Generated the admin password (shown at the end)." || true
}

detect_gpu() {
  COMPOSE=(docker compose)
  GPU_ON=0
  if [ "$USE_GPU" = "cpu" ]; then
    info "GPU use is switched off (--cpu)."
    return
  fi
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
    COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.gpu.yml)
    GPU_ON=1
    info "NVIDIA GPU found: the language model will use it."
  else
    info "No NVIDIA GPU found: the language model will run on the CPU."
  fi
}

start_ollama() {
  if "${COMPOSE[@]}" up -d ollama; then
    return
  fi
  if [ "$GPU_ON" = "1" ]; then
    warn "Docker could not use the GPU (the NVIDIA Container Toolkit or WSL 2 GPU support may be missing). Continuing on the CPU."
    COMPOSE=(docker compose)
    GPU_ON=0
    "${COMPOSE[@]}" up -d ollama
  else
    fail "The language model service did not start. See: docker compose logs ollama"
  fi
}

pull_model() {
  step "Downloading the local language model ($MODEL)"
  info "This is a one-time download of several gigabytes, so it can take a while."
  local tries=0
  until "${COMPOSE[@]}" exec -T ollama ollama list >/dev/null 2>&1; do
    tries=$((tries + 1))
    [ "$tries" -gt 30 ] && fail "The language model service is not answering. See: docker compose logs ollama"
    sleep 2
  done
  "${COMPOSE[@]}" exec -T ollama ollama pull "$MODEL"
  info "Model ready."
}

start_services() {
  step "Building and starting the database, API and dashboard"
  info "The first build downloads and compiles everything, so it can take several minutes."
  start_ollama
  "${COMPOSE[@]}" up -d --build db api dashboard
  printf '    Waiting for the API'
  wait_healthy mednexa-api 300
  printf '\n    API is healthy.\n'
}

load_demo() {
  step "Loading the demo hospital, doctors and bookings"
  "${COMPOSE[@]}" --profile demo run --rm seed
}

link_hospital() {
  step "Linking the phone line to the hospital"
  local id
  id="$("${COMPOSE[@]}" exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select id from hospital order by created_at limit 1"' 2>/dev/null | tr -d '[:space:]' || true)"
  if printf '%s' "$id" | grep -Eq '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'; then
    set_env MEDNEXA_TEL_HOSPITAL_ID "$id"
    info "Hospital $id linked."
  else
    warn "No hospital exists yet. Create it in the dashboard (Settings), copy its id into MEDNEXA_TEL_HOSPITAL_ID in .env, then run: docker compose up -d telephony"
  fi
}

start_telephony() {
  step "Starting the voice service"
  info "The first start downloads the speech models, so it can take a few minutes."
  "${COMPOSE[@]}" up -d --build telephony
  printf '    Waiting for the voice service'
  wait_healthy mednexa-telephony 900
  printf '\n    Voice service is ready.\n'
}

summary() {
  local email password
  email="$(get_env MEDNEXA_ADMIN_EMAIL)"
  password="$(get_env MEDNEXA_ADMIN_PASSWORD)"
  printf '\n%s%sMedNexa is running.%s\n\n' "$GREEN" "$BOLD" "$RESET"
  printf '  Dashboard     http://localhost:3001\n'
  printf '  Test a call   http://localhost:8001/call   (allow the microphone, use headphones)\n'
  printf '  API docs      http://localhost:8000/docs\n\n'
  printf '  Sign in with  %s\n' "$email"
  printf '  Password      %s   (also in .env)\n\n' "$password"
  printf '%sStop:%s   docker compose down\n' "$DIM" "$RESET"
  printf '%sStart:%s  docker compose up -d\n' "$DIM" "$RESET"
  if [ "${GPU_ON:-0}" = "1" ]; then
    printf '%sStart again with the GPU:%s docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d\n' "$DIM" "$RESET"
  fi
  if [ "${GPU_ON:-0}" = "0" ] && [ "$PULL_MODEL" = "1" ] && [ -z "$(get_env MEDNEXA_AGENT_GROQ_API_KEY)$(get_env MEDNEXA_AGENT_OPENAI_API_KEY)" ]; then
    printf '\n%sThe local model runs on the CPU here, so replies will be slow. For faster replies add\n' "$YELLOW"
    printf 'a cloud key (MEDNEXA_AGENT_GROQ_API_KEY, or the OPENAI key and base URL) to .env\n'
    printf 'and run: docker compose up -d telephony%s\n' "$RESET"
  fi
}

main() {
  while [ $# -gt 0 ]; do
    case "$1" in
      --model) [ $# -ge 2 ] || fail "--model needs a model name"; MODEL="$2"; shift ;;
      --cpu) USE_GPU="cpu" ;;
      --no-model) PULL_MODEL=0 ;;
      --no-seed) SEED_DEMO=0 ;;
      --no-start) START_STACK=0 ;;
      -h|--help) usage; exit 0 ;;
      *) usage; fail "Unknown option: $1" ;;
    esac
    shift
  done

  trap on_error ERR

  printf '%sMedNexa setup%s\n' "$BOLD" "$RESET"
  check_docker
  prepare_env

  step "Checking for a GPU"
  detect_gpu

  if [ "$START_STACK" = "0" ]; then
    printf '\nConfiguration is ready in .env. Run ./setup.sh again without --no-start to start everything.\n'
    return
  fi

  start_services
  [ "$SEED_DEMO" = "1" ] && load_demo
  link_hospital
  [ "$PULL_MODEL" = "1" ] && pull_model
  start_telephony
  summary
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  main "$@"
fi
