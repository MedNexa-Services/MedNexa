"""Call sessions and transcripts: written by the call pipeline, read by the dashboard."""

import uuid
from datetime import datetime

from fastapi import APIRouter, status

from app.api.deps import DbSession, Paging
from app.models import CallOutcome
from app.schemas.call import (
    CallLogCreate,
    CallLogOut,
    CallSessionCreate,
    CallSessionDetailOut,
    CallSessionEnd,
    CallSessionOut,
)
from app.schemas.common import Page, Phone
from app.services import call_service

router = APIRouter(tags=["calls"])


@router.post("/calls", status_code=status.HTTP_201_CREATED)
async def start_call(db: DbSession, body: CallSessionCreate) -> CallSessionOut:
    return CallSessionOut.model_validate(await call_service.start_call(db, body))


@router.post("/calls/{session_id}/logs", status_code=status.HTTP_201_CREATED)
async def append_log(db: DbSession, session_id: uuid.UUID, body: CallLogCreate) -> CallLogOut:
    return CallLogOut.model_validate(await call_service.append_log(db, session_id, body))


@router.post("/calls/{session_id}/end")
async def end_call(db: DbSession, session_id: uuid.UUID, body: CallSessionEnd) -> CallSessionOut:
    return CallSessionOut.model_validate(await call_service.end_call(db, session_id, body))


@router.get("/calls")
async def list_calls(
    db: DbSession,
    paging: Paging,
    hospital_id: uuid.UUID | None = None,
    caller_phone: Phone | None = None,
    outcome: CallOutcome | None = None,
    escalated: bool | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
) -> Page[CallSessionOut]:
    """Newest first. Pass timezone-aware datetimes for the started_* bounds."""
    items, total = await call_service.list_calls(
        db,
        hospital_id=hospital_id,
        caller_phone=caller_phone,
        outcome=outcome,
        escalated=escalated,
        started_after=started_after,
        started_before=started_before,
        limit=paging.limit,
        offset=paging.offset,
    )
    return Page(items=items, total=total, limit=paging.limit, offset=paging.offset)


@router.get("/calls/{session_id}")
async def get_call(db: DbSession, session_id: uuid.UUID) -> CallSessionDetailOut:
    return await call_service.get_call(db, session_id)
