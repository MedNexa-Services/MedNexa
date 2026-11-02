import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainValidationError, NotFound
from app.models import Schedule
from app.schemas.schedule import ScheduleOverrideIn
from app.services.slot_service import load_doctor, working_window


async def list_overrides(
    db: AsyncSession, doctor_id: uuid.UUID, date_from: date | None, date_to: date | None
) -> list[Schedule]:
    await load_doctor(db, doctor_id)
    stmt = select(Schedule).where(Schedule.doctor_id == doctor_id)
    if date_from:
        stmt = stmt.where(Schedule.date >= date_from)
    if date_to:
        stmt = stmt.where(Schedule.date <= date_to)
    return list(await db.scalars(stmt.order_by(Schedule.date)))


async def upsert_override(
    db: AsyncSession, doctor_id: uuid.UUID, data: ScheduleOverrideIn
) -> Schedule:
    doctor = await load_doctor(db, doctor_id)
    candidate = Schedule(doctor_id=doctor_id, **data.model_dump())
    if data.is_available and working_window(doctor, data.date, candidate) is None:
        raise DomainValidationError("Override hours leave no working time on that date")

    values = insert(Schedule).values(doctor_id=doctor_id, **data.model_dump())
    stmt = values.on_conflict_do_update(
        constraint="uq_schedule_doctor_id_date",
        set_={
            "is_available": values.excluded.is_available,
            "start_time": values.excluded.start_time,
            "end_time": values.excluded.end_time,
            "override_reason": values.excluded.override_reason,
            "updated_at": func.now(),
        },
    ).returning(Schedule)
    override: Schedule = (
        await db.scalars(stmt, execution_options={"populate_existing": True})
    ).one()
    await db.commit()
    return override


async def delete_override(db: AsyncSession, doctor_id: uuid.UUID, on: date) -> None:
    override = await db.scalar(
        select(Schedule).where(Schedule.doctor_id == doctor_id, Schedule.date == on)
    )
    if override is None:
        raise NotFound("No schedule override for that date")
    await db.delete(override)
    await db.commit()
