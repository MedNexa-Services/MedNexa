from enum import StrEnum
from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMMode(StrEnum):
    AUTO = "auto"  # local first, cloud on slowness/failure (and for Hindi if enabled)
    LOCAL = "local"  # never call the cloud (FORCE_LOCAL)
    CLOUD = "cloud"  # never call the local model (FORCE_CLOUD)


class CloudProvider(StrEnum):
    GROQ = "groq"
    OPENAI = "openai"


class AgentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEDNEXA_AGENT_", env_file=".env", extra="ignore")

    llm_mode: LLMMode = LLMMode.AUTO

    # Local model (Ollama)
    ollama_url: str = "http://localhost:11434"
    local_model: str = "llama3.1:8b"

    # Cloud model
    cloud_provider: CloudProvider = CloudProvider.GROQ
    cloud_model: str = "llama-3.3-70b-versatile"
    groq_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None

    # ModelRouter behaviour
    max_latency_seconds: float = 3.0  # local call is abandoned for cloud after this
    cloud_timeout_seconds: float = 15.0
    circuit_failure_threshold: int = 3  # consecutive local failures before skipping local
    circuit_open_seconds: float = 300.0
    hindi_prefers_cloud: bool = True

    # Agent loop
    temperature: float = 0.2
    max_tool_rounds: int = 6  # LLM <-> tool round trips per caller turn
    max_history_messages: int = 40  # older turns are dropped from the LLM context
    max_response_chars: int = 600  # replies are spoken; keep them short


@lru_cache
def get_settings() -> AgentSettings:
    return AgentSettings()
