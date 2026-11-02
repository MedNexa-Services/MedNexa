import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import CallOutcome, CallRole


class CallSession(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "call_session"

    hospital_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hospital.id", ondelete="CASCADE"), index=True
    )
    caller_phone: Mapped[str] = mapped_column(String(20), index=True)
    call_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    call_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    language_detected: Mapped[str | None] = mapped_column(String(10))
    call_outcome: Mapped[CallOutcome | None] = mapped_column(Enum(CallOutcome, name="call_outcome"))
    summary: Mapped[str | None] = mapped_column(Text)
    escalated_to_human: Mapped[bool] = mapped_column(server_default=text("false"))
    total_turns: Mapped[int] = mapped_column(server_default=text("0"))


class CallLog(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "call_log"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("call_session.id", ondelete="CASCADE"), index=True
    )
    appointment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("appointment.id", ondelete="SET NULL")
    )
    role: Mapped[CallRole] = mapped_column(Enum(CallRole, name="call_role"))
    content: Mapped[str] = mapped_column(Text)
    tool_called: Mapped[str | None] = mapped_column(String(100))
    tool_result: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
