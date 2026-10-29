"""Agent interface — stub for Part 2's MedNexaAgent.

Part 3 (this module) drives the full call pipeline but must stay decoupled from
Part 2's LangGraph agent so both can be developed and tested independently.

This file defines the ``AgentInterface`` protocol, a ``StubAgent`` that returns
hard-coded responses, and ``create_agent``, which the pipeline uses to build one
agent per call: Part 2's ``MedNexaAgent`` when the ``agent`` package is
installed (``uv sync --extra agent``), otherwise the stub, with a warning.
Set ``MEDNEXA_TEL_USE_STUB_AGENT=true`` to force the stub.

The interface Part 2 must implement:
    async def get_greeting(self) -> str
    async def process(self, text: str, language: str) -> str
    async def get_summary(self) -> str | None
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from telephony.logging_setup import get_logger

log = get_logger("agent")


@runtime_checkable
class AgentInterface(Protocol):
    """Protocol that Part 2's MedNexaAgent must satisfy."""

    async def get_greeting(self) -> str:
        """Return the opening greeting in the caller's default language."""
        ...

    async def process(self, text: str, language: str) -> str:
        """Process a caller utterance and return the agent's response."""
        ...

    async def get_summary(self) -> str | None:
        """Return a brief summary of what was accomplished on this call."""
        ...


class StubAgent:
    """Minimal stub used during development / unit tests.

    Responds with a canned greeting and echoes back what the caller says.
    Replace with Part 2's real agent in production.
    """

    def __init__(self, caller_phone: str = "", hospital_id: str = "") -> None:
        self.caller_phone = caller_phone
        self.hospital_id = hospital_id
        self._turn = 0

    async def get_greeting(self) -> str:
        return (
            "Hello! Thank you for calling MedNexa. "
            "I am your AI receptionist. How may I help you today?"
        )

    async def process(self, text: str, language: str) -> str:
        self._turn += 1
        log.info("stub_agent_process", turn=self._turn, text=text[:60], language=language)
        if not text.strip():
            return "I'm sorry, I didn't catch that. Could you please repeat?"
        return (
            f"Thank you for saying: '{text}'. "
            "I'm currently in test mode. Is there anything else I can help you with?"
        )

    async def get_summary(self) -> str | None:
        return f"Test call completed after {self._turn} turn(s)."


def create_agent(caller_phone: str, hospital_id: str) -> AgentInterface:
    """One agent per call: Part 2's MedNexaAgent if available, else the stub."""
    from telephony.config import get_settings

    if not get_settings().use_stub_agent:
        try:
            from agent import MedNexaAgent  # Part 2 (optional dependency)
        except ImportError:
            log.warning("mednexa_agent_unavailable", fallback="StubAgent")
        else:
            agent: AgentInterface = MedNexaAgent(caller_phone, hospital_id)
            return agent
    return StubAgent(caller_phone, hospital_id)
