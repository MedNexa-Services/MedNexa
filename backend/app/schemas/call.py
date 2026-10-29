import uuid
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field

from app.core.normalize import normalize_phone
from app.models.enums import CallOutcome, CallRole
from app.schemas.common import ORMModel

ANONYMOUS_CALLER = "anonymous"


def _caller_id(value: str) -> str:
    """Normalized caller number, or 'anonymous' when the number is withheld or invalid.

    Calls from hidden numbers must still be answered and logged.
    """
    try:
        return normalize_phone(value)
    except ValueError:
        return ANONYMOUS_CALLER


CallerId = Annotated[str, AfterValidator(_caller_id)]


class CallSessionCreate(BaseModel):
    hospital_id: uuid.UUID
    caller_phone: CallerId
    language_detected: str | None = Field(default=None, max_length=10)


class CallLogCreate(BaseModel):
    role: CallRole
    content: str
    tool_called: str | None = Field(default=None, max_length=100)
    tool_result: str | None = None
    appointment_id: uuid.UUID | None = None


class CallSessionEnd(BaseModel):
    call_outcome: CallOutcome
    summary: str | None = None
    language_detected: str | None = Field(default=None, max_length=10)
    escalated_to_human: bool = False


class CallLogOut(ORMModel):
    id: uuid.UUID
    session_id: uuid.UUID
    appointment_id: uuid.UUID | None
    role: CallRole
    content: str
    tool_called: str | None
    tool_result: str | None
    timestamp: datetime


class CallSessionOut(ORMModel):
    id: uuid.UUID
    hospital_id: uuid.UUID
    caller_phone: str
    call_start: datetime
    call_end: datetime | None
    language_detected: str | None
    call_outcome: CallOutcome | None
    summary: str | None
    escalated_to_human: bool
    total_turns: int


class CallSessionDetailOut(CallSessionOut):
    logs: list[CallLogOut]
