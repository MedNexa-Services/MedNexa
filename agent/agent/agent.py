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

RETRY = {
    "en": "I'm sorry, I lost my connection for a moment. Could you please say that again?",
    "hi": "माफ़ कीजिए, कनेक्शन में थोड़ी दिक्कत हुई। कृपया दोबारा कहिए।",
}
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
            confirm_changes=self.settings.confirm_changes,
        )
        self._failed_turns = 0
        self.language = "en"
        self.fixed_language: str | None = None
        self._hospital: HospitalContext | None = None
        self._pending: list[AnyMessage] = []
        self._lock = asyncio.Lock()
        self._config: RunnableConfig = {"configurable": {"thread_id": str(uuid.uuid4())}}
        self._graph = build_graph(self.router, self.ctx, self.settings, self._system_prompt)

    async def get_greeting(self) -> str:
        try:
            hospital: HospitalContext | None = await self._hospital_context()
        except Exception:
            logger.exception("hospital_context_failed hospital_id=%s", self.ctx.hospital_id)
            hospital = None
        text = greeting(hospital, self.fixed_language)
        self._pending.append(AIMessage(content=text))
        return text

    async def process(self, text: str, language: str = "en") -> str:
        async with self._lock:
            self.language = self.fixed_language or detect_language(
                text, hint=normalize_language(language) or self.language
            )
            if not text.strip():
                return await self._reply_for_empty()
            pending = self._pending
            state: AgentState = {
                "messages": [*pending, HumanMessage(content=text)],
                "language": self.language,
                "tool_rounds": 0,
            }
            self._pending = []
            self.ctx.turn += 1
            self.ctx.last_caller_text = text
            self.ctx.readback = None
            self.ctx.done = None
            try:
                result = await self._graph.ainvoke(state, self._config)
            except Exception:
                logger.exception("agent_turn_failed")
                self._pending = pending
                self._failed_turns += 1
                if self._failed_turns >= self.settings.handover_after_failures:
                    self.ctx.escalation_reason = "Agent error"
                    return TROUBLE.get(self.language, TROUBLE["en"])
                return RETRY.get(self.language, RETRY["en"])
            self._failed_turns = 0
            reply = result["messages"][-1]
            return reply.text if isinstance(reply, AIMessage) else str(reply.content)

    async def get_summary(self) -> str | None:
        summary = self.ctx.events.summary()
        if self.ctx.escalation_reason and not self.ctx.events.escalated:
            summary = f"{summary or ''} Escalated: {self.ctx.escalation_reason}.".strip()
        return summary

    @property
    def speech_hints(self) -> str | None:
        h = self._hospital
        if h is None:
            return None
        doctors = ", ".join(f"Dr. {d.name.removeprefix('Dr. ')}" for d in h.doctors)
        return (
            f"Call to {h.name}. Doctors: {doctors}. "
            f"Departments: {', '.join(h.departments)}. Appointment booking: "
            "patient name, age, gender male or female."
        )

    @property
    def escalated(self) -> bool:
        return self.ctx.escalation_reason is not None

    @property
    def call_outcome(self) -> str:
        return "ESCALATED" if self.escalated else self.ctx.events.outcome()

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
        return render_system_prompt(
            hospital, language, now, fixed_language=self.fixed_language is not None
        )

    async def _reply_for_empty(self) -> str:
        return (
            "माफ़ कीजिए, मुझे सुनाई नहीं दिया। कृपया दोबारा कहें।"
            if self.language == "hi"
            else "Sorry, I didn't catch that. Could you please repeat?"
        )
