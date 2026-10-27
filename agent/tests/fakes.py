"""Deterministic stand-ins for LLM providers."""

import asyncio
from collections.abc import Callable, Sequence
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

Reply = AIMessage | Exception | Callable[[Sequence[BaseMessage]], AIMessage]


class ScriptedProvider:
    """Returns pre-scripted replies in order and records what it was sent.

    A reply can be an AIMessage, an exception to raise, or a callable that
    builds the AIMessage from the messages it receives.
    """

    def __init__(self, name: str, replies: Sequence[Reply] = (), *, delay: float = 0.0):
        self.name = name
        self.replies = list(replies)
        self.delay = delay
        self.calls: list[tuple[list[BaseMessage], list[dict[str, Any]]]] = []

    async def ainvoke(
        self, messages: Sequence[BaseMessage], tools: Sequence[dict[str, Any]]
    ) -> AIMessage:
        self.calls.append((list(messages), list(tools)))
        if self.delay:
            await asyncio.sleep(self.delay)
        if not self.replies:
            raise AssertionError(f"{self.name}: no scripted reply left")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        if callable(reply):
            return reply(messages)
        return reply


def say(text: str) -> AIMessage:
    return AIMessage(content=text)


def call(name: str, call_id: str = "call_1", **args: Any) -> AIMessage:
    """An AIMessage requesting a single tool call."""
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])
