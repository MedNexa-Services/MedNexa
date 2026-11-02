import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFound
from app.core.timeutils import add_minutes, generate_time_slots, hospital_now
from app.models import Appointment, AppointmentStatus, Doctor, Hospital, Schedule
from app.schemas.slot import DoctorSlotOut, SlotOut

NEXT_AVAILABLE_HORIZON_DAYS = 14


@dataclass(frozen=True)
class DayPlan:
    grid: list[time]
    booked: dict[time, uuid.UUID]
    cap_reached: bool
    not_before: time | None
    is_past_date: bool

    def is_free(self, at: time) -> bool:
        return (
            not self.is_past_date
            and not self.cap_reached
            and at in self.grid
            and at not in self.booked
            and (self.not_before is None or at > self.not_before)
        )

    def free_slots(self) -> list[time]:
        return [t for t in self.grid if self.is_free(t)]


def working_window(doctor: Doctor, on: date, override: Schedule | None) -> tuple[time, time] | None:
    if override is not None:
        if not override.is_available:
            return None
        start = override.start_time or doctor.slot_start_time
        end = override.end_time or doctor.slot_end_time
        return (start, end) if end > start else None
    if on.isoweekday() in doctor.available_days:
        return doctor.slot_start_time, doctor.slot_end_time
    return None


def plan_day(
    doctor: Doctor,
    on: date,
    override: Schedule | None,
    booked: dict[time, uuid.UUID],
    now: datetime,
) -> DayPlan:
    window = working_window(doctor, on, override)
    grid = generate_time_slots(*window, doctor.slot_duration_minutes) if window else []
    today = now.date()
    return DayPlan(
        grid=grid,
        booked=booked,
        cap_reached=len(booked) >= doctor.max_daily_appointments,
        not_before=now.time() if on == today else None,
        is_past_date=on < today,
    )


async def load_doctor(db: AsyncSession, doctor_id: uuid.UUID) -> Doctor:
    doctor = await db.scalar(
        select(Doctor).where(Doctor.id == doctor_id).options(selectinload(Doctor.hospital))
    )
    if doctor is None:
        raise NotFound("Doctor not found")
    return doctor


def is_bookable_doctor(doctor: Doctor) -> bool:
    return doctor.is_active and doctor.hospital.is_active


async def load_day_plan(
    db: AsyncSession, doctor: Doctor, on: date, now: datetime | None = None
) -> DayPlan:
    now = now or hospital_now(doctor.hospital.timezone)
    override = await db.scalar(
        select(Schedule).where(Schedule.doctor_id == doctor.id, Schedule.date == on)
    )
    rows = await db.execute(
        select(Appointment.appointment_time, Appointment.patient_id).where(
            Appointment.doctor_id == doctor.id,
            Appointment.appointment_date == on,
            Appointment.status == AppointmentStatus.BOOKED,
        )
    )
    booked = {t: pid for t, pid in rows}
    return plan_day(doctor, on, override, booked, now)


async def get_available_slots(
    db: AsyncSession, doctor_id: uuid.UUID, on: date, *, now: datetime | None = None
) -> list[SlotOut]:
    doctor = await load_doctor(db, doctor_id)
    if not is_bookable_doctor(doctor):
        return []
    plan = await load_day_plan(db, doctor, on, now)
    duration = doctor.slot_duration_minutes
    return [SlotOut(start=t, end=add_minutes(t, duration)) for t in plan.free_slots()]


async def find_next_available(
    db: AsyncSession,
    hospital_id: uuid.UUID,
    speciality: str,
    from_date: date | None = None,
    limit: int = 5,
    *,
    now: datetime | None = None,
) -> list[DoctorSlotOut]:
    hospital = await db.get(Hospital, hospital_id)
    if hospital is None:
        raise NotFound("Hospital not found")
    speciality = speciality.strip()
    if not hospital.is_active or limit <= 0 or not speciality:
        return []
    now = now or hospital_now(hospital.timezone)
    start = max(from_date or now.date(), now.date())
    end = start + timedelta(days=NEXT_AVAILABLE_HORIZON_DAYS - 1)

    doctors = list(
        await db.scalars(
            select(Doctor)
            .where(
                Doctor.hospital_id == hospital_id,
                Doctor.is_active,
                or_(
                    Doctor.speciality.icontains(speciality, autoescape=True),
                    Doctor.department.icontains(speciality, autoescape=True),
                ),
            )
            .order_by(Doctor.name)
        )
    )
    if not doctors:
        return []
    doctor_ids = [d.id for d in doctors]

    overrides = {
        (s.doctor_id, s.date): s
        for s in await db.scalars(
            select(Schedule).where(
                Schedule.doctor_id.in_(doctor_ids), Schedule.date.between(start, end)
            )
        )
    }
    booked: dict[tuple[uuid.UUID, date], dict[time, uuid.UUID]] = {}
    rows = await db.execute(
        select(
            Appointment.doctor_id,
            Appointment.appointment_date,
            Appointment.appointment_time,
            Appointment.patient_id,
        ).where(
            Appointment.doctor_id.in_(doctor_ids),
            Appointment.appointment_date.between(start, end),
            Appointment.status == AppointmentStatus.BOOKED,
        )
    )
    for doctor_id, on, at, patient_id in rows:
        booked.setdefault((doctor_id, on), {})[at] = patient_id

    results: list[DoctorSlotOut] = []
    day = start
    while day <= end and len(results) < limit:
        day_slots = []
        for doctor in doctors:
            plan = plan_day(
                doctor, day, overrides.get((doctor.id, day)), booked.get((doctor.id, day), {}), now
            )
            for t in plan.free_slots():
                day_slots.append(
                    DoctorSlotOut(
                        doctor_id=doctor.id,
                        doctor_name=doctor.name,
                        speciality=doctor.speciality,
                        department=doctor.department,
                        date=day,
                        start=t,
                        end=add_minutes(t, doctor.slot_duration_minutes),
                    )
                )
        day_slots.sort(key=lambda s: (s.start, s.doctor_name))
        results.extend(day_slots)
        day += timedelta(days=1)
    return results[:limit]
