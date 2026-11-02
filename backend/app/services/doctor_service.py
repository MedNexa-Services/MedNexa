import uuid
from datetime import timedelta

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DomainValidationError
from app.core.timeutils import hospital_now
from app.models import Doctor, Schedule
from app.schemas.doctor import DoctorCreate, DoctorDetailOut, DoctorOut, DoctorUpdate
from app.schemas.schedule import ScheduleOverrideOut
from app.services.common import apply_updates, paginate
from app.services.hospital_service import get_hospital
from app.services.slot_service import load_doctor

UPCOMING_OVERRIDE_DAYS = 30


async def create_doctor(db: AsyncSession, data: DoctorCreate) -> Doctor:
    await get_hospital(db, data.hospital_id)
    doctor = Doctor(**data.model_dump())
    db.add(doctor)
    await db.commit()
    await db.refresh(doctor)
    return doctor


def _doctor_query(
    hospital_id: uuid.UUID | None,
    speciality: str | None,
    department: str | None,
    include_inactive: bool,
) -> Select[Doctor]:
    stmt = select(Doctor)
    if hospital_id:
        stmt = stmt.where(Doctor.hospital_id == hospital_id)
    if speciality and speciality.strip():
        stmt = stmt.where(Doctor.speciality.icontains(speciality.strip(), autoescape=True))
    if department and department.strip():
        stmt = stmt.where(Doctor.department.icontains(department.strip(), autoescape=True))
    if not include_inactive:
        stmt = stmt.where(Doctor.is_active)
    return stmt.order_by(Doctor.name)


async def search_doctors(
    db: AsyncSession,
    hospital_id: uuid.UUID | None = None,
    speciality: str | None = None,
    department: str | None = None,
    *,
    include_inactive: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Doctor], int]:
    stmt = _doctor_query(hospital_id, speciality, department, include_inactive)
    return await paginate(db, stmt, limit, offset)


async def list_doctors(
    db: AsyncSession,
    hospital_id: uuid.UUID,
    speciality: str | None = None,
    department: str | None = None,
) -> list[DoctorOut]:
    stmt = _doctor_query(hospital_id, speciality, department, include_inactive=False)
    return [DoctorOut.model_validate(d) for d in await db.scalars(stmt)]


async def get_doctor(db: AsyncSession, doctor_id: uuid.UUID) -> DoctorDetailOut:
    doctor = await load_doctor(db, doctor_id)
    today = hospital_now(doctor.hospital.timezone).date()
    overrides = await db.scalars(
        select(Schedule)
        .where(
            Schedule.doctor_id == doctor_id,
            Schedule.date.between(today, today + timedelta(days=UPCOMING_OVERRIDE_DAYS)),
        )
        .order_by(Schedule.date)
    )
    return DoctorDetailOut.model_validate(
        {
            **DoctorOut.model_validate(doctor).model_dump(),
            "upcoming_overrides": [ScheduleOverrideOut.model_validate(o) for o in overrides],
        }
    )


async def update_doctor(db: AsyncSession, doctor_id: uuid.UUID, data: DoctorUpdate) -> Doctor:
    doctor = await load_doctor(db, doctor_id)
    apply_updates(doctor, data.model_dump(exclude_unset=True))
    if doctor.slot_end_time <= doctor.slot_start_time:
        raise DomainValidationError("slot_end_time must be after slot_start_time")
    await db.commit()
    await db.refresh(doctor)
    return doctor


async def deactivate_doctor(db: AsyncSession, doctor_id: uuid.UUID) -> None:
    doctor = await load_doctor(db, doctor_id)
    doctor.is_active = False
    await db.commit()
