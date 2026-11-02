import asyncio
import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from langchain_core.messages import AIMessage, BaseMessage

from agent.config import AgentSettings, CloudProvider, LLMMode

logger = logging.getLogger(__name__)


class ChatProvider(Protocol):
    name: str

    async def ainvoke(
        self, messages: Sequence[BaseMessage], tools: Sequence[dict[str, Any]]
    ) -> AIMessage: ...


class LangChainProvider:
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


def _rate_limited(exc: BaseException) -> bool:
    return getattr(exc, "status_code", None) == 429


def _transient(exc: BaseException) -> bool:
    status = getattr(exc, "status_code", None)
    return (
        isinstance(exc, ConnectionError | json.JSONDecodeError)
        or "Connection" in type(exc).__name__
        or "Timeout" in type(exc).__name__
        or (isinstance(status, int) and (status == 429 or status >= 500))
    )


class SpilloverProvider:
    def __init__(self, providers: Sequence[ChatProvider]) -> None:
        self._providers = list(providers)
        self.name = self._providers[0].name

    async def ainvoke(
        self, messages: Sequence[BaseMessage], tools: Sequence[dict[str, Any]]
    ) -> AIMessage:
        for provider in self._providers[:-1]:
            try:
                result = await provider.ainvoke(messages, tools)
            except Exception as exc:
                if not (_rate_limited(exc) or _transient(exc)):
                    raise
                logger.info(
                    "llm_model_skipped provider=%s error=%s", provider.name, type(exc).__name__
                )
                continue
            self.name = provider.name
            return result
        last = self._providers[-1]
        self.name = last.name
        return await last.ainvoke(messages, tools)


class NoProviderAvailable(RuntimeError):
    pass


@dataclass
class RouterStats:
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
        s = self._settings
        last_error: BaseException | None = None
        for index, (provider, timeout) in enumerate(attempts):
            is_last = index + 1 == len(attempts)
            tries = 1 + (s.llm_retries if is_last else 0)
            for attempt in range(tries):
                start = self._clock()
                try:
                    async with asyncio.timeout(timeout):
                        result = await provider.ainvoke(messages, tools)
                except Exception as exc:
                    last_error = exc
                    if attempt + 1 < tries and _transient(exc):
                        logger.warning(
                            "llm_call_retry provider=%s error=%s attempt=%d",
                            provider.name,
                            type(exc).__name__,
                            attempt + 1,
                        )
                        await asyncio.sleep(s.llm_retry_delay_seconds * 2**attempt)
                        continue
                    self._record_failure(provider)
                    logger.warning(
                        "llm_call_failed provider=%s error=%s fallback=%s",
                        provider.name,
                        type(exc).__name__,
                        not is_last,
                    )
                    break
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
    local: ChatProvider | None = None
    if settings.llm_mode != LLMMode.CLOUD:
        from langchain_ollama import ChatOllama

        local = LangChainProvider(
            f"ollama:{settings.local_model}",
            ChatOllama(
                model=settings.local_model,
                base_url=settings.ollama_url,
                temperature=settings.temperature,
                num_ctx=settings.local_context_tokens,
                keep_alive=settings.local_keep_alive,
            ),
        )

    cloud: ChatProvider | None = None
    if settings.llm_mode != LLMMode.LOCAL:
        if settings.cloud_provider == CloudProvider.GROQ and settings.groq_api_key:
            from langchain_groq import ChatGroq

            cloud = _cloud_models(
                settings,
                "groq",
                lambda model, retries: ChatGroq(
                    model_name=model,
                    api_key=settings.groq_api_key,
                    temperature=settings.temperature,
                    reasoning_effort=settings.cloud_reasoning_effort,
                    max_retries=retries,
                    timeout=settings.cloud_request_timeout_seconds,
                ),
            )
        elif settings.cloud_provider == CloudProvider.OPENAI and settings.openai_api_key:
            from langchain_openai import ChatOpenAI

            cloud = _cloud_models(
                settings,
                "openai",
                lambda model, retries: ChatOpenAI(
                    model=model,
                    api_key=settings.openai_api_key,
                    base_url=settings.openai_base_url,
                    temperature=settings.temperature,
                    reasoning_effort=settings.cloud_reasoning_effort,
                    max_retries=retries,
                    timeout=settings.cloud_request_timeout_seconds,
                ),
            )
    return ModelRouter(settings, local, cloud)


def _cloud_models(
    settings: AgentSettings, prefix: str, make: Callable[[str, int], Any]
) -> ChatProvider:
    models = [settings.cloud_model, *settings.cloud_fallback_models]
    providers: list[ChatProvider] = [
        LangChainProvider(f"{prefix}:{model}", make(model, 0)) for model in models
    ]
    return providers[0] if len(providers) == 1 else SpilloverProvider(providers)
