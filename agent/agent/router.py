"""ModelRouter: one interface over the local (Ollama) and cloud (Groq/OpenAI) LLMs.

Routing per call:
  1. LLM_MODE=local / cloud forces one side.
  2. Hindi turns go to the cloud when `hindi_prefers_cloud` (better quality).
  3. Otherwise try local, bounded by `max_latency_seconds`; on timeout or error,
     answer from the cloud instead.
  4. Circuit breaker: after `circuit_failure_threshold` consecutive local
     failures, skip local for `circuit_open_seconds`.

Every call's provider and latency are logged.
"""

import asyncio
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from langchain_core.messages import AIMessage, BaseMessage

from agent.config import AgentSettings, CloudProvider, LLMMode

logger = logging.getLogger(__name__)


class ChatProvider(Protocol):
    """Anything that turns messages (+ tool schemas) into an AIMessage."""

    name: str

    async def ainvoke(
        self, messages: Sequence[BaseMessage], tools: Sequence[dict[str, Any]]
    ) -> AIMessage: ...


class LangChainProvider:
    """Adapts a LangChain chat model (ChatOllama, ChatGroq, ChatOpenAI) to ChatProvider."""

    def __init__(self, name: str, model: Any) -> None:
        self.name = name
        self._model = model

    async def ainvoke(
        self, messages: Sequence[BaseMessage], tools: Sequence[dict[str, Any]]
    ) -> AIMessage:
        runnable = self._model.bind_tools(list(tools)) if tools else self._model
        result = await runnable.ainvoke(list(messages))
        if not isinstance(result, AIMessage):
            raise TypeError(f"{self.name} returned {type(result).__name__}, not AIMessage")
        return result


class NoProviderAvailable(RuntimeError):
    pass


@dataclass
class RouterStats:
    """Recent routing decisions, exposed for logging/monitoring."""

    calls: dict[str, int] = field(default_factory=dict)
    fallbacks: int = 0
    last_latency_ms: int | None = None
    last_provider: str | None = None


class ModelRouter:
    def __init__(
        self,
        settings: AgentSettings,
        local: ChatProvider | None,
        cloud: ChatProvider | None,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if local is None and cloud is None:
            raise NoProviderAvailable("Configure a local model, a cloud model, or both")
        self._settings = settings
        self._local = local
        self._cloud = cloud
        self._clock = clock
        self._local_failures = 0
        self._circuit_open_until = 0.0
        self.stats = RouterStats()

    @property
    def circuit_open(self) -> bool:
        return self._clock() < self._circuit_open_until

    def _choose(self, language: str) -> list[tuple[ChatProvider, float]]:
        """Ordered (provider, timeout) attempts for this call."""
        s = self._settings
        if s.llm_mode == LLMMode.LOCAL:
            order = [self._local]
        elif s.llm_mode == LLMMode.CLOUD:
            order = [self._cloud]
        elif self.circuit_open or (language == "hi" and s.hindi_prefers_cloud):
            order = [self._cloud, self._local]
        else:
            order = [self._local, self._cloud]
        providers = [p for p in order if p is not None]
        # The latency cap only applies to the local model when a cloud attempt follows;
        # when it is the last option, a slow answer beats none.
        return [
            (
                p,
                s.max_latency_seconds
                if p is self._local and i < len(providers) - 1
                else s.cloud_timeout_seconds,
            )
            for i, p in enumerate(providers)
        ]

    async def ainvoke(
        self,
        messages: Sequence[BaseMessage],
        tools: Sequence[dict[str, Any]] = (),
        *,
        language: str = "en",
    ) -> AIMessage:
        attempts = self._choose(language)
        if not attempts:
            raise NoProviderAvailable(f"No model available for LLM mode {self._settings.llm_mode}")
        last_error: BaseException | None = None
        for index, (provider, timeout) in enumerate(attempts):
            start = self._clock()
            try:
                async with asyncio.timeout(timeout):
                    result = await provider.ainvoke(messages, tools)
            except Exception as exc:  # includes TimeoutError from the latency cap
                last_error = exc
                self._record_failure(provider)
                logger.warning(
                    "llm_call_failed provider=%s error=%s fallback=%s",
                    provider.name,
                    type(exc).__name__,
                    index + 1 < len(attempts),
                )
                continue
            latency_ms = int((self._clock() - start) * 1000)
            self._record_success(provider, latency_ms, fallback=index > 0)
            return result
        raise NoProviderAvailable("All configured models failed") from last_error

    def _record_success(self, provider: ChatProvider, latency_ms: int, *, fallback: bool) -> None:
        if provider is self._local:
            self._local_failures = 0
        self.stats.calls[provider.name] = self.stats.calls.get(provider.name, 0) + 1
        self.stats.fallbacks += int(fallback)
        self.stats.last_latency_ms = latency_ms
        self.stats.last_provider = provider.name
        logger.info("llm_call provider=%s latency_ms=%d", provider.name, latency_ms)

    def _record_failure(self, provider: ChatProvider) -> None:
        if provider is not self._local:
            return
        self._local_failures += 1
        if self._local_failures >= self._settings.circuit_failure_threshold:
            self._circuit_open_until = self._clock() + self._settings.circuit_open_seconds
            self._local_failures = 0
            logger.warning("llm_circuit_open seconds=%s", self._settings.circuit_open_seconds)


def build_router(settings: AgentSettings) -> ModelRouter:
    """Router with real providers from settings. Cloud is only set up when its API
    key is present; local is skipped when LLM_MODE=cloud."""
    local: ChatProvider | None = None
    if settings.llm_mode != LLMMode.CLOUD:
        from langchain_ollama import ChatOllama

        local = LangChainProvider(
            f"ollama:{settings.local_model}",
            ChatOllama(
                model=settings.local_model,
                base_url=settings.ollama_url,
                temperature=settings.temperature,
            ),
        )

    cloud: ChatProvider | None = None
    if settings.llm_mode != LLMMode.LOCAL:
        if settings.cloud_provider == CloudProvider.GROQ and settings.groq_api_key:
            from langchain_groq import ChatGroq

            cloud = LangChainProvider(
                f"groq:{settings.cloud_model}",
                ChatGroq(
                    model_name=settings.cloud_model,
                    api_key=settings.groq_api_key,
                    temperature=settings.temperature,
                ),
            )
        elif settings.cloud_provider == CloudProvider.OPENAI and settings.openai_api_key:
            from langchain_openai import ChatOpenAI

            cloud = LangChainProvider(
                f"openai:{settings.cloud_model}",
                ChatOpenAI(
                    model=settings.cloud_model,
                    api_key=settings.openai_api_key,
                    temperature=settings.temperature,
                ),
            )
    return ModelRouter(settings, local, cloud)
