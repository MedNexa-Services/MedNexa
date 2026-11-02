from __future__ import annotations

from typing import Protocol, runtime_checkable

from telephony.logging_setup import get_logger

log = get_logger("agent")


@runtime_checkable
class AgentInterface(Protocol):
    async def get_greeting(self) -> str: ...

    async def process(self, text: str, language: str) -> str: ...

    async def get_summary(self) -> str | None: ...

    @property
    def call_outcome(self) -> str: ...

    @property
    def escalated(self) -> bool: ...


class StubAgent:
    call_outcome: str = "OTHER"
    escalated: bool = False

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
    from telephony.config import get_settings

    if not get_settings().use_stub_agent:
        try:
            from agent import MedNexaAgent
        except ImportError:
            log.warning("mednexa_agent_unavailable", fallback="StubAgent")
        else:
            agent: AgentInterface = MedNexaAgent(caller_phone, hospital_id)
            return agent
    return StubAgent(caller_phone, hospital_id)
