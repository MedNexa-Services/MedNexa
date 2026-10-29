import pytest
from langchain_core.messages import HumanMessage

from agent.config import AgentSettings, LLMMode
from agent.router import ModelRouter, NoProviderAvailable
from tests.fakes import ScriptedProvider, say

MESSAGES = [HumanMessage("hi")]


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def settings(**kw) -> AgentSettings:
    return AgentSettings(_env_file=None, **kw)


async def test_local_first_in_auto_mode() -> None:
    local, cloud = ScriptedProvider("local", [say("from local")]), ScriptedProvider("cloud")
    router = ModelRouter(settings(), local, cloud)
    assert (await router.ainvoke(MESSAGES)).content == "from local"
    assert cloud.calls == []
    assert router.stats.last_provider == "local"


async def test_slow_local_falls_back_to_cloud() -> None:
    local = ScriptedProvider("local", [say("too late")], delay=0.2)
    cloud = ScriptedProvider("cloud", [say("from cloud")])
    router = ModelRouter(settings(max_latency_seconds=0.05), local, cloud)
    assert (await router.ainvoke(MESSAGES)).content == "from cloud"
    assert router.stats.fallbacks == 1


async def test_local_error_falls_back_to_cloud() -> None:
    local = ScriptedProvider("local", [ConnectionError("ollama down")])
    cloud = ScriptedProvider("cloud", [say("from cloud")])
    router = ModelRouter(settings(), local, cloud)
    assert (await router.ainvoke(MESSAGES)).content == "from cloud"


async def test_hindi_prefers_cloud() -> None:
    local, cloud = ScriptedProvider("local"), ScriptedProvider("cloud", [say("नमस्ते")])
    router = ModelRouter(settings(), local, cloud)
    await router.ainvoke(MESSAGES, language="hi")
    assert local.calls == []


async def test_hindi_uses_local_when_preference_disabled() -> None:
    local, cloud = ScriptedProvider("local", [say("ok")]), ScriptedProvider("cloud")
    router = ModelRouter(settings(hindi_prefers_cloud=False), local, cloud)
    await router.ainvoke(MESSAGES, language="hi")
    assert cloud.calls == []


async def test_circuit_breaker_skips_local_then_recovers() -> None:
    clock = FakeClock()
    local = ScriptedProvider("local", [RuntimeError()] * 3 + [say("local again")])
    cloud = ScriptedProvider("cloud", [say("c1"), say("c2"), say("c3"), say("c4")])
    router = ModelRouter(
        settings(circuit_failure_threshold=3, circuit_open_seconds=60), local, cloud, clock=clock
    )
    for _ in range(3):
        await router.ainvoke(MESSAGES)
    assert router.circuit_open

    await router.ainvoke(MESSAGES)  # local skipped while open
    assert len(local.calls) == 3

    clock.now += 61
    assert (await router.ainvoke(MESSAGES)).content == "local again"


async def test_success_resets_failure_count() -> None:
    local = ScriptedProvider("local", [RuntimeError(), say("ok"), RuntimeError(), RuntimeError()])
    cloud = ScriptedProvider("cloud", [say("c")] * 3)
    router = ModelRouter(settings(circuit_failure_threshold=3), local, cloud)
    for _ in range(4):
        await router.ainvoke(MESSAGES)
    assert not router.circuit_open


async def test_forced_local_never_calls_cloud() -> None:
    local = ScriptedProvider("local", [RuntimeError("down")])
    cloud = ScriptedProvider("cloud", [say("x")])
    router = ModelRouter(settings(llm_mode=LLMMode.LOCAL), local, cloud)
    with pytest.raises(NoProviderAvailable):
        await router.ainvoke(MESSAGES, language="hi")
    assert cloud.calls == []


async def test_forced_cloud_never_calls_local() -> None:
    local, cloud = ScriptedProvider("local"), ScriptedProvider("cloud", [say("x")])
    router = ModelRouter(settings(llm_mode=LLMMode.CLOUD), local, cloud)
    await router.ainvoke(MESSAGES)
    assert local.calls == []


async def test_local_only_setup_works_without_cloud() -> None:
    router = ModelRouter(settings(), ScriptedProvider("local", [say("ok")]), None)
    assert (await router.ainvoke(MESSAGES, language="hi")).content == "ok"


async def test_all_failing_raises() -> None:
    router = ModelRouter(
        settings(),
        ScriptedProvider("local", [RuntimeError()]),
        ScriptedProvider("cloud", [RuntimeError()]),
    )
    with pytest.raises(NoProviderAvailable):
        await router.ainvoke(MESSAGES)


def test_router_needs_a_provider() -> None:
    with pytest.raises(NoProviderAvailable):
        ModelRouter(settings(), None, None)


async def test_tools_are_passed_to_provider() -> None:
    local = ScriptedProvider("local", [say("ok")])
    tool = {"type": "function", "function": {"name": "t", "parameters": {}}}
    await ModelRouter(settings(), local, None).ainvoke(MESSAGES, [tool])
    assert local.calls[0][1] == [tool]


def test_build_router_wires_providers_from_settings() -> None:
    from agent.router import build_router

    local_only = build_router(settings())
    assert local_only._local is not None and local_only._cloud is None  # no API key

    groq = build_router(settings(groq_api_key="test-key"))
    assert groq._cloud is not None and groq._cloud.name == "groq:llama-3.3-70b-versatile"

    openai_only = build_router(
        settings(llm_mode="cloud", cloud_provider="openai", openai_api_key="k", cloud_model="m")
    )
    assert openai_only._local is None and openai_only._cloud.name == "openai:m"

    with pytest.raises(NoProviderAvailable):  # cloud forced but no key configured
        build_router(settings(llm_mode="cloud"))


async def test_langchain_provider_adapts_chat_models() -> None:
    from langchain_core.language_models.fake_chat_models import GenericFakeChatModel

    from agent.router import LangChainProvider

    model = GenericFakeChatModel(messages=iter([say("hello from a chat model")]))
    provider = LangChainProvider("fake", model)
    assert (await provider.ainvoke(MESSAGES, [])).content == "hello from a chat model"


async def test_slow_local_is_not_cut_off_when_there_is_no_cloud() -> None:
    local = ScriptedProvider("local", [say("slow but fine")], delay=0.1)
    router = ModelRouter(settings(max_latency_seconds=0.05), local, None)
    assert (await router.ainvoke(MESSAGES)).content == "slow but fine"


async def test_local_after_cloud_is_not_latency_capped() -> None:
    local = ScriptedProvider("local", [say("local answer")], delay=0.1)
    cloud = ScriptedProvider("cloud", [RuntimeError("cloud down")])
    router = ModelRouter(settings(max_latency_seconds=0.05), local, cloud)
    assert (await router.ainvoke(MESSAGES, language="hi")).content == "local answer"
