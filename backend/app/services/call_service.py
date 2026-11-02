import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainValidationError, NotFound
from app.models import CallLog, CallOutcome, CallRole, CallSession
from app.schemas.call import (
    CallLogCreate,
    CallLogOut,
    CallSessionCreate,
    CallSessionDetailOut,
    CallSessionEnd,
    CallSessionOut,
)
from app.services.common import paginate
from app.services.hospital_service import get_hospital

_CONVERSATION_ROLES = {CallRole.USER, CallRole.ASSISTANT}


async def _get_session(
    db: AsyncSession, session_id: uuid.UUID, *, lock: bool = False
) -> CallSession:
    session = await db.get(CallSession, session_id, with_for_update=lock, populate_existing=lock)
    if session is None:
        raise NotFound("Call session not found")
    return session


async def start_call(db: AsyncSession, data: CallSessionCreate) -> CallSession:
    await get_hospital(db, data.hospital_id)
    session = CallSession(**data.model_dump())
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def append_log(db: AsyncSession, session_id: uuid.UUID, data: CallLogCreate) -> CallLog:
    try:
        session = await _get_session(db, session_id, lock=True)
        if session.call_end is not None:
            raise DomainValidationError("Call has already ended")
        log = CallLog(session_id=session_id, **data.model_dump())
        db.add(log)
        if data.role in _CONVERSATION_ROLES:
            session.total_turns += 1
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(log)
    return log


async def end_call(db: AsyncSession, session_id: uuid.UUID, data: CallSessionEnd) -> CallSession:
    try:
        session = await _get_session(db, session_id, lock=True)
        if session.call_end is not None:
            raise DomainValidationError("Call has already ended")
        session.call_end = datetime.now(UTC)
        session.call_outcome = data.call_outcome
        session.summary = data.summary
        session.escalated_to_human = data.escalated_to_human
        if data.language_detected:
            session.language_detected = data.language_detected
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(session)
    return session


async def purge_calls_older_than(db: AsyncSession, days: int) -> int:
    if days < 1:
        raise ValueError("days must be at least 1")
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = await db.execute(delete(CallSession).where(CallSession.call_start < cutoff))
    await db.commit()
    return result.rowcount or 0  # type: ignore[attr-defined]


async def close_stale_calls(db: AsyncSession, minutes: int = 30) -> int:
    cutoff = datetime.now(UTC) - timedelta(minutes=minutes)
    last_said = (
        select(func.max(CallLog.timestamp)).where(CallLog.session_id == CallSession.id)
    ).scalar_subquery()
    result = await db.execute(
        update(CallSession)
        .where(CallSession.call_end.is_(None), CallSession.call_start < cutoff)
        .values(
            call_end=func.coalesce(last_said, CallSession.call_start),
            call_outcome=func.coalesce(CallSession.call_outcome, CallOutcome.ABANDONED),
        )
    )
    await db.commit()
    return result.rowcount or 0  # type: ignore[attr-defined]


async def list_calls(
    db: AsyncSession,
    *,
    hospital_id: uuid.UUID | None = None,
    caller_phone: str | None = None,
    outcome: CallOutcome | None = None,
    escalated: bool | None = None,
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[CallSessionOut], int]:
    stmt = select(CallSession)
    if hospital_id:
        stmt = stmt.where(CallSession.hospital_id == hospital_id)
    if caller_phone:
        stmt = stmt.where(CallSession.caller_phone == caller_phone)
    if outcome:
        stmt = stmt.where(CallSession.call_outcome == outcome)
    if escalated is not None:
        stmt = stmt.where(CallSession.escalated_to_human == escalated)
    if started_after:
        stmt = stmt.where(CallSession.call_start >= started_after)
    if started_before:
        stmt = stmt.where(CallSession.call_start < started_before)
    sessions, total = await paginate(
        db, stmt.order_by(CallSession.call_start.desc()), limit, offset
    )
    return [CallSessionOut.model_validate(s) for s in sessions], total


async def get_call(db: AsyncSession, session_id: uuid.UUID) -> CallSessionDetailOut:
    session = await _get_session(db, session_id)
    logs = await db.scalars(
        select(CallLog).where(CallLog.session_id == session_id).order_by(CallLog.timestamp)
    )
    return CallSessionDetailOut.model_validate(
        {
            **CallSessionOut.model_validate(session).model_dump(),
            "logs": [CallLogOut.model_validate(log) for log in logs],
        }
    )
