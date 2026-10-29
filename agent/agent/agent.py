"""MedNexaAgent: one instance per phone call.

Implements Part 3's AgentInterface (telephony/telephony/agent_interface.py):

    agent = MedNexaAgent(caller_phone, hospital_id)
    await agent.get_greeting()
    await agent.process(text, language)   # language from STT: "en" / "hi"
    await agent.get_summary()

Plus `call_outcome` and `escalated` for ending the call session in the backend.
"""

import asyncio
import logging
import uuid
from collections.abc import Callable
from datetime import datetime

from app.core.normalize import normalize_phone
from app.core.timeutils import hospital_now
from app.database import SessionFactory
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent.config import AgentSettings, get_settings
from agent.graph import AgentState, build_graph
from agent.language import detect_language, normalize_language
from agent.prompts import HospitalContext, greeting, load_hospital_context, render_system_prompt
from agent.router import ModelRouter, build_router
from agent.tools import ToolContext

logger = logging.getLogger(__name__)

TROUBLE = {
    "en": (
        "I'm sorry, I'm having trouble right now. Let me connect you to our staff; "
        "please stay on the line."
    ),
    "hi": "माफ़ कीजिए, अभी तकनीकी समस्या है। मैं आपको स्टाफ से जोड़ रही हूँ, कृपया लाइन पर बने रहें।",
}


class MedNexaAgent:
    def __init__(
        self,
        caller_phone: str,
        hospital_id: str | uuid.UUID,
        *,
        router: ModelRouter | None = None,
        settings: AgentSettings | None = None,
        session_factory: async_sessionmaker[AsyncSession] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.router = router or build_router(self.settings)
        self._session_factory = session_factory or SessionFactory
        self._now = now
        try:
            phone: str | None = normalize_phone(caller_phone) if caller_phone else None
        except ValueError:
            logger.warning("caller_phone_unparseable")
            phone = None
        self.ctx = ToolContext(
            hospital_id=uuid.UUID(str(hospital_id)),
            caller_phone=phone,
            session_factory=self._session_factory,
            now=now,
        )
        self.language = "en"
        self._hospital: HospitalContext | None = None
        self._pending: list[AnyMessage] = []  # greeting, added to history on first turn
        self._lock = asyncio.Lock()
        self._config: RunnableConfig = {"configurable": {"thread_id": str(uuid.uuid4())}}
        self._graph = build_graph(self.router, self.ctx, self.settings, self._system_prompt)

    # --- AgentInterface -------------------------------------------------------------

    async def get_greeting(self) -> str:
        try:
            hospital: HospitalContext | None = await self._hospital_context()
        except Exception:  # never fail the call before it starts
            logger.exception("hospital_context_failed hospital_id=%s", self.ctx.hospital_id)
            hospital = None
        text = greeting(hospital)
        self._pending.append(AIMessage(content=text))
        return text

    async def process(self, text: str, language: str = "en") -> str:
        """Handle one caller utterance and return the reply to speak."""
        async with self._lock:
            self.language = detect_language(
                text, hint=normalize_language(language) or self.language
            )
            if not text.strip():
                return await self._reply_for_empty()
            state: AgentState = {
                "messages": [*self._pending, HumanMessage(content=text)],
                "language": self.language,
                "tool_rounds": 0,
            }
            self._pending = []
            try:
                result = await self._graph.ainvoke(state, self._config)
            except Exception:
                logger.exception("agent_turn_failed")
                self.ctx.escalation_reason = "Agent error"
                return TROUBLE.get(self.language, TROUBLE["en"])
            reply = result["messages"][-1]
            return reply.text if isinstance(reply, AIMessage) else str(reply.content)

    async def get_summary(self) -> str | None:
        summary = self.ctx.events.summary()
        if self.ctx.escalation_reason and not self.ctx.events.escalated:
            summary = f"{summary or ''} Escalated: {self.ctx.escalation_reason}.".strip()
        return summary

    # --- extras for the call pipeline -----------------------------------------------

    @property
    def escalated(self) -> bool:
        return self.ctx.escalation_reason is not None

    @property
    def call_outcome(self) -> str:
        """Backend CallOutcome value (BOOKED, CANCELLED, ..., ESCALATED, OTHER)."""
        return "ESCALATED" if self.escalated else self.ctx.events.outcome()

    # --- internals ------------------------------------------------------------------

    async def _hospital_context(self) -> HospitalContext:
        if self._hospital is None:
            async with self._session_factory() as db:
                self._hospital = await load_hospital_context(
                    db, self.ctx.hospital_id, self._now() if self._now else None
                )
        return self._hospital

    async def _system_prompt(self, language: str) -> str:
        hospital = await self._hospital_context()
        now = self._now() if self._now else hospital_now(hospital.timezone)
        return render_system_prompt(hospital, language, now)

    async def _reply_for_empty(self) -> str:
        return (
            "माफ़ कीजिए, मुझे सुनाई नहीं दिया। कृपया दोबारा कहें।"
            if self.language == "hi"
            else "Sorry, I didn't catch that. Could you please repeat?"
        )
