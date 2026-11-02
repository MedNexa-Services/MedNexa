import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import DbSession, Paging
from app.schemas.common import Page
from app.schemas.doctor import DoctorCreate, DoctorDetailOut, DoctorOut, DoctorUpdate
from app.schemas.schedule import ScheduleOverrideIn, ScheduleOverrideOut
from app.services import doctor_service, schedule_service

router = APIRouter(tags=["doctors"])


@router.get("/doctors")
async def list_doctors(
    db: DbSession,
    paging: Paging,
    hospital_id: uuid.UUID | None = None,
    speciality: str | None = None,
    department: str | None = None,
    include_inactive: Annotated[bool, Query()] = False,
) -> Page[DoctorOut]:
    items, total = await doctor_service.search_doctors(
        db,
        hospital_id,
        speciality,
        department,
        include_inactive=include_inactive,
        limit=paging.limit,
        offset=paging.offset,
    )
    return Page(
        items=[DoctorOut.model_validate(d) for d in items],
        total=total,
        limit=paging.limit,
        offset=paging.offset,
    )


@router.post("/doctors", status_code=status.HTTP_201_CREATED)
async def create_doctor(db: DbSession, body: DoctorCreate) -> DoctorOut:
    return DoctorOut.model_validate(await doctor_service.create_doctor(db, body))


@router.get("/doctors/{doctor_id}")
async def get_doctor(db: DbSession, doctor_id: uuid.UUID) -> DoctorDetailOut:
    return await doctor_service.get_doctor(db, doctor_id)


@router.patch("/doctors/{doctor_id}")
async def update_doctor(db: DbSession, doctor_id: uuid.UUID, body: DoctorUpdate) -> DoctorOut:
    """Template changes affect future availability only; existing appointments are kept."""
    return DoctorOut.model_validate(await doctor_service.update_doctor(db, doctor_id, body))


@router.delete("/doctors/{doctor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_doctor(db: DbSession, doctor_id: uuid.UUID) -> None:
    """Soft delete: no new bookings; existing appointments are left for staff to handle."""
    await doctor_service.deactivate_doctor(db, doctor_id)


@router.get("/doctors/{doctor_id}/schedule", tags=["schedules"])
async def list_overrides(
    db: DbSession,
    doctor_id: uuid.UUID,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> list[ScheduleOverrideOut]:
    overrides = await schedule_service.list_overrides(db, doctor_id, date_from, date_to)
    return [ScheduleOverrideOut.model_validate(o) for o in overrides]


@router.put("/doctors/{doctor_id}/schedule", tags=["schedules"])
async def upsert_override(
    db: DbSession, doctor_id: uuid.UUID, body: ScheduleOverrideIn
) -> ScheduleOverrideOut:
    """Create or replace the override for `body.date`. Existing appointments are not moved."""
    return ScheduleOverrideOut.model_validate(
        await schedule_service.upsert_override(db, doctor_id, body)
    )


@router.delete(
    "/doctors/{doctor_id}/schedule/{on}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["schedules"],
)
async def delete_override(db: DbSession, doctor_id: uuid.UUID, on: date) -> None:
    await schedule_service.delete_override(db, doctor_id, on)
