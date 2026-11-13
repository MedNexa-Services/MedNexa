from enum import StrEnum
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMMode(StrEnum):
    AUTO = "auto"
    LOCAL = "local"
    CLOUD = "cloud"


class CloudProvider(StrEnum):
    GROQ = "groq"
    OPENAI = "openai"


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEDNEXA_AGENT_", env_file=".env", extra="ignore")

    llm_mode: LLMMode = LLMMode.AUTO

    ollama_url: str = "http://localhost:11434"
    local_model: str = "llama3.1:8b"
    local_context_tokens: int = 8192
    local_keep_alive: str = "1h"

    cloud_provider: CloudProvider = CloudProvider.GROQ
    cloud_model: str = "openai/gpt-oss-20b"
    cloud_fallback_models: list[str] = []
    cloud_reasoning_effort: str | None = None
    groq_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    openai_base_url: str | None = None

    max_latency_seconds: float = 3.0
    cloud_timeout_seconds: float = 40.0
    cloud_request_timeout_seconds: float = 10.0
    circuit_failure_threshold: int = 3
    circuit_open_seconds: float = 300.0
    hindi_prefers_cloud: bool = True

    llm_retries: int = 2
    llm_retry_delay_seconds: float = 0.7

    temperature: float = 0.2
    handover_after_failures: int = 3
    confirm_changes: bool = True
    max_tool_rounds: int = 6
    max_history_messages: int = 40
    max_response_chars: int = 350


@lru_cache
def get_settings() -> AgentSettings:
    return AgentSettings()
