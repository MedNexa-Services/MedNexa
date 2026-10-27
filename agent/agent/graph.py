"""LangGraph agent graph (task 2.5).

    START -> agent --(tool calls)--> tools -> agent ...
                 \\--(final text)---> guardrail -> END

- agent:     system prompt (rebuilt each step with the current language and time)
             + recent history -> ModelRouter -> AIMessage
- tools:     runs every requested tool call against the service layer
- guardrail: validates the final reply (agent/guardrails.py) and replaces it if needed

Conversation memory is kept per call by the checkpointer (thread_id = call id).
"""

import json
from collections.abc import Awaitable, Callable, Sequence
from typing import Annotated, Any, TypedDict

from langchain_core.messages import (
    AIMessage,
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from agent.config import AgentSettings
from agent.guardrails import apply_guardrails
from agent.router import ModelRouter
from agent.tools import TOOLS, ToolContext, execute_tool

FINAL_ANSWER_NOTE = (
    "Tool limit reached for this turn. Reply to the caller now without calling tools; "
    "if something is unresolved, say you will connect them to staff."
)


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    language: str
    tool_rounds: int


def recent_history(messages: Sequence[BaseMessage], limit: int) -> list[BaseMessage]:
    """The last `limit` messages, never starting with a tool result or a tool-calling
    message, so no tool result is separated from the request that produced it."""

    def orphaned(m: BaseMessage) -> bool:
        return isinstance(m, ToolMessage) or (isinstance(m, AIMessage) and bool(m.tool_calls))

    window: list[BaseMessage] = list(messages[-limit:])
    while window and orphaned(window[0]):
        window.pop(0)
    if window:
        return window
    last_caller_turn: list[BaseMessage] = [m for m in messages if isinstance(m, HumanMessage)]
    return last_caller_turn[-1:]


def build_graph(
    router: ModelRouter,
    ctx: ToolContext,
    settings: AgentSettings,
    system_prompt: Callable[[str], Awaitable[str]],
) -> CompiledStateGraph[AgentState, None, AgentState, AgentState]:
    schemas = [t.schema() for t in TOOLS]

    async def agent_node(state: AgentState) -> dict[str, Any]:
        language = state["language"]
        messages: list[BaseMessage] = [SystemMessage(await system_prompt(language))]
        messages += recent_history(state["messages"], settings.max_history_messages)
        tools: list[dict[str, Any]] = schemas
        if state["tool_rounds"] >= settings.max_tool_rounds:
            messages.append(SystemMessage(FINAL_ANSWER_NOTE))
            tools = []
        reply = await router.ainvoke(messages, tools, language=language)
        if not tools and reply.tool_calls:  # model ignored the limit: drop the calls
            reply = AIMessage(content=reply.content, id=reply.id)
        return {"messages": [reply]}

    async def tools_node(state: AgentState) -> dict[str, Any]:
        last = state["messages"][-1]
        assert isinstance(last, AIMessage)
        results = []
        for tool_call in last.tool_calls:
            result = await execute_tool(ctx, tool_call["name"], tool_call["args"])
            results.append(
                ToolMessage(
                    content=json.dumps(result, ensure_ascii=False),
                    tool_call_id=tool_call["id"] or tool_call["name"],
                    name=tool_call["name"],
                )
            )
        return {"messages": results, "tool_rounds": state["tool_rounds"] + 1}

    async def guardrail_node(state: AgentState) -> dict[str, Any]:
        last = state["messages"][-1]
        assert isinstance(last, AIMessage)
        checked = apply_guardrails(
            last.text, ctx.events, state["language"], max_chars=settings.max_response_chars
        )
        if not checked.changed:
            return {}
        # Same id -> add_messages replaces the reply, so history matches what was spoken.
        return {"messages": [AIMessage(content=checked.text, id=last.id)]}

    def route_after_agent(state: AgentState) -> str:
        last = state["messages"][-1]
        return "tools" if isinstance(last, AIMessage) and last.tool_calls else "guardrail"

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("guardrail", guardrail_node)
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", route_after_agent, ["tools", "guardrail"])
    graph.add_edge("tools", "agent")
    graph.add_edge("guardrail", END)
    return graph.compile(checkpointer=InMemorySaver())
