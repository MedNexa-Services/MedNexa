import re
import uuid
from datetime import UTC, date, datetime, time

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    Conflict,
    DailyCapReached,
    DomainError,
    DomainValidationError,
    DuplicateBooking,
    InvalidSlot,
    NotCancellable,
    NotFound,
    NotOwner,
    SlotUnavailable,
)
from app.core.normalize import normalize_name, normalize_phone
from app.core.timeutils import hospital_now
from app.models import Appointment, AppointmentStatus, BookingSource, Doctor, Hospital, Patient
from app.schemas.appointment import AppointmentOut, BookingConfirmation, BookingRequest
from app.services.common import paginate
from app.services.patient_service import find_patient, find_patient_by_sound, upsert_patient
from app.services.slot_service import DayPlan, is_bookable_doctor, load_day_plan

SLOT_INDEX = "uq_appointment_doctor_slot_booked"


async def _lock_doctor(db: AsyncSession, doctor_id: uuid.UUID) -> Doctor:
    doctor = await db.scalar(
        select(Doctor)
        .where(Doctor.id == doctor_id)
        .options(selectinload(Doctor.hospital))
        .with_for_update(of=Doctor)
    )
    if doctor is None:
        raise NotFound("Doctor not found")
    return doctor


async def _lock_appointment(db: AsyncSession, appointment_id: uuid.UUID) -> Appointment:
    appt = await db.scalar(
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .options(
            selectinload(Appointment.patient),
            selectinload(Appointment.doctor).selectinload(Doctor.hospital),
        )
        .with_for_update(of=Appointment)
    )
    if appt is None:
        raise NotFound("Appointment not found")
    return appt


async def _doctor_id_of(db: AsyncSession, appointment_id: uuid.UUID) -> uuid.UUID:
    doctor_id = await db.scalar(
        select(Appointment.doctor_id).where(Appointment.id == appointment_id)
    )
    if doctor_id is None:
        raise NotFound("Appointment not found")
    return doctor_id


def _check_slot(plan: DayPlan, at: time, patient_id: uuid.UUID) -> None:
    if plan.is_past_date or (plan.not_before is not None and at <= plan.not_before):
        raise InvalidSlot("That time has already passed")
    if not plan.grid:
        raise InvalidSlot("The doctor is not available on that date")
    if at not in plan.grid:
        raise InvalidSlot("That time is not one of the doctor's appointment slots")
    holder = plan.booked.get(at)
    if holder == patient_id:
        raise DuplicateBooking("This patient already has this appointment")
    if holder is not None:
        raise SlotUnavailable("That slot is already booked")
    if plan.cap_reached:
        raise DailyCapReached("The doctor is fully booked for that day")


async def _next_token(db: AsyncSession, doctor_id: uuid.UUID, on: date) -> int:
    current = await db.scalar(
        select(func.max(Appointment.token_number)).where(
            Appointment.doctor_id == doctor_id, Appointment.appointment_date == on
        )
    )
    return (current or 0) + 1


async def _insert_appointment(
    db: AsyncSession,
    doctor: Doctor,
    patient: Patient,
    on: date,
    at: time,
    *,
    source: BookingSource,
    notes: str | None,
    rescheduled_from_id: uuid.UUID | None = None,
) -> Appointment:
    appt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        hospital_id=doctor.hospital_id,
        appointment_date=on,
        appointment_time=at,
        slot_duration_minutes=doctor.slot_duration_minutes,
        status=AppointmentStatus.BOOKED,
        booking_source=source,
        notes=notes,
        token_number=await _next_token(db, doctor.id, on),
        rescheduled_from_id=rescheduled_from_id,
    )
    appt.patient = patient
    appt.doctor = doctor
    db.add(appt)
    await db.flush()
    await db.refresh(appt, ["created_at", "updated_at"])
    return appt


def _map_integrity_error(exc: IntegrityError) -> DomainError:
    if SLOT_INDEX in str(exc.orig):
        return SlotUnavailable("That slot is already booked")
    return Conflict("The booking conflicts with existing data")


def _ensure_owner(appt: Appointment, caller_phone: str) -> None:
    try:
        phone = normalize_phone(caller_phone)
    except ValueError as exc:
        raise DomainValidationError("Invalid phone number") from exc
    if appt.patient.phone != phone:
        raise NotOwner("This appointment is not registered to the calling phone number")


def _ensure_changeable(appt: Appointment, *, allow_past: bool, now: datetime | None) -> None:
    if appt.status != AppointmentStatus.BOOKED:
        raise NotCancellable(f"Appointment is {appt.status.value.lower()}, not booked")
    if allow_past:
        return
    now = now or hospital_now(appt.doctor.hospital.timezone)
    starts = datetime.combine(appt.appointment_date, appt.appointment_time, now.tzinfo)
    if starts <= now:
        raise NotCancellable("Appointment time has already passed")


async def book_appointment(
    db: AsyncSession, req: BookingRequest, *, now: datetime | None = None
) -> BookingConfirmation:
    try:
        doctor = await _lock_doctor(db, req.doctor_id)
        if not is_bookable_doctor(doctor):
            raise DomainValidationError("This doctor is not accepting appointments")
        patient = await upsert_patient(db, doctor.hospital_id, req.patient)
        plan = await load_day_plan(db, doctor, req.appointment_date, now)
        _check_slot(plan, req.appointment_time, patient.id)
        appt = await _insert_appointment(
            db,
            doctor,
            patient,
            req.appointment_date,
            req.appointment_time,
            source=req.booking_source,
            notes=req.notes,
        )
        confirmation = BookingConfirmation.from_model(appt)
        await db.commit()
        return confirmation
    except IntegrityError as exc:
        await db.rollback()
        raise _map_integrity_error(exc) from exc
    except Exception:
        await db.rollback()
        raise


async def _cancel(
    db: AsyncSession,
    appointment_id: uuid.UUID,
    reason: str | None,
    *,
    caller_phone: str | None,
    now: datetime | None,
) -> AppointmentOut:
    try:
        appt = await _lock_appointment(db, appointment_id)
        if caller_phone is not None:
            _ensure_owner(appt, caller_phone)
        _ensure_changeable(appt, allow_past=caller_phone is None, now=now)
        appt.status = AppointmentStatus.CANCELLED
        appt.cancelled_at = datetime.now(UTC)
        appt.cancellation_reason = reason
        await db.flush()
        out = AppointmentOut.from_model(appt)
        await db.commit()
        return out
    except Exception:
        await db.rollback()
        raise


async def cancel_appointment(
    db: AsyncSession,
    appointment_id: uuid.UUID,
    caller_phone: str,
    reason: str | None = None,
    *,
    now: datetime | None = None,
) -> AppointmentOut:
    return await _cancel(db, appointment_id, reason, caller_phone=caller_phone, now=now)


async def cancel_appointment_by_staff(
    db: AsyncSession, appointment_id: uuid.UUID, reason: str | None = None
) -> AppointmentOut:
    return await _cancel(db, appointment_id, reason, caller_phone=None, now=None)


async def _reschedule(
    db: AsyncSession,
    appointment_id: uuid.UUID,
    new_date: date,
    new_time: time,
    *,
    caller_phone: str | None,
    now: datetime | None,
) -> BookingConfirmation:
    try:
        doctor = await _lock_doctor(db, await _doctor_id_of(db, appointment_id))
        old = await _lock_appointment(db, appointment_id)
        if caller_phone is not None:
            _ensure_owner(old, caller_phone)
        _ensure_changeable(old, allow_past=caller_phone is None, now=now)
        if not is_bookable_doctor(doctor):
            raise DomainValidationError("This doctor is not accepting appointments")
        if (old.appointment_date, old.appointment_time) == (new_date, new_time):
            raise InvalidSlot("The new time is the same as the current appointment")

        old.status = AppointmentStatus.RESCHEDULED
        await db.flush()
        plan = await load_day_plan(db, doctor, new_date, now)
        _check_slot(plan, new_time, old.patient_id)
        new = await _insert_appointment(
            db,
            doctor,
            old.patient,
            new_date,
            new_time,
            source=old.booking_source,
            notes=old.notes,
            rescheduled_from_id=old.id,
        )
        confirmation = BookingConfirmation.from_model(new)
        await db.commit()
        return confirmation
    except IntegrityError as exc:
        await db.rollback()
        raise _map_integrity_error(exc) from exc
    except Exception:
        await db.rollback()
        raise


async def reschedule_appointment(
    db: AsyncSession,
    appointment_id: uuid.UUID,
    caller_phone: str,
    new_date: date,
    new_time: time,
    *,
    now: datetime | None = None,
) -> BookingConfirmation:
    return await _reschedule(
        db, appointment_id, new_date, new_time, caller_phone=caller_phone, now=now
    )


async def reschedule_appointment_by_staff(
    db: AsyncSession, appointment_id: uuid.UUID, new_date: date, new_time: time
) -> BookingConfirmation:
    return await _reschedule(db, appointment_id, new_date, new_time, caller_phone=None, now=None)


async def get_patient_appointments(
    db: AsyncSession,
    hospital_id: uuid.UUID,
    phone: str,
    patient_name: str,
    upcoming_only: bool = True,
    *,
    now: datetime | None = None,
) -> list[AppointmentOut]:
    try:
        phone = normalize_phone(phone)
    except ValueError:
        return []
    patient = await find_patient(db, hospital_id, phone, patient_name)
    if patient is None:
        patient = await find_patient_by_sound(db, hospital_id, phone, patient_name)
    if patient is None:
        return []
    query = (
        select(Appointment)
        .where(Appointment.patient_id == patient.id)
        .options(selectinload(Appointment.patient), selectinload(Appointment.doctor))
        .order_by(Appointment.appointment_date, Appointment.appointment_time)
    )
    if upcoming_only:
        if now is None:
            tz = await db.scalar(select(Hospital.timezone).where(Hospital.id == hospital_id))
            now = hospital_now(tz or "Asia/Kolkata")
        today = now.date()
        query = query.where(
            Appointment.status == AppointmentStatus.BOOKED,
            or_(
                Appointment.appointment_date > today,
                and_(
                    Appointment.appointment_date == today,
                    Appointment.appointment_time > now.time(),
                ),
            ),
        )
    return [AppointmentOut.from_model(a) for a in await db.scalars(query)]


async def get_appointment(db: AsyncSession, appointment_id: uuid.UUID) -> AppointmentOut:
    appt = await db.scalar(
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .options(selectinload(Appointment.patient), selectinload(Appointment.doctor))
    )
    if appt is None:
        raise NotFound("Appointment not found")
    return AppointmentOut.from_model(appt)


async def list_appointments(
    db: AsyncSession,
    *,
    hospital_id: uuid.UUID | None = None,
    doctor_id: uuid.UUID | None = None,
    patient_id: uuid.UUID | None = None,
    on: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    status: AppointmentStatus | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AppointmentOut], int]:
    stmt = select(Appointment).options(
        selectinload(Appointment.patient), selectinload(Appointment.doctor)
    )
    if hospital_id:
        stmt = stmt.where(Appointment.hospital_id == hospital_id)
    if doctor_id:
        stmt = stmt.where(Appointment.doctor_id == doctor_id)
    if patient_id:
        stmt = stmt.where(Appointment.patient_id == patient_id)
    if on:
        stmt = stmt.where(Appointment.appointment_date == on)
    if date_from:
        stmt = stmt.where(Appointment.appointment_date >= date_from)
    if date_to:
        stmt = stmt.where(Appointment.appointment_date <= date_to)
    if status:
        stmt = stmt.where(Appointment.status == status)
    if q and q.strip():
        matches = [Patient.normalized_name.contains(normalize_name(q), autoescape=True)]
        digits = re.sub(r"\D", "", q)
        if len(digits) >= 3:
            matches.append(Patient.phone.contains(digits, autoescape=True))
        if q.strip().isdigit():
            matches.append(Appointment.token_number == int(q))
        stmt = stmt.join(Appointment.patient).where(or_(*matches))
    stmt = stmt.order_by(
        Appointment.appointment_date, Appointment.appointment_time, Appointment.token_number
    )
    appts, total = await paginate(db, stmt, limit, offset)
    return [AppointmentOut.from_model(a) for a in appts], total
