from datetime import date, time, timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.normalize import normalize_name
from app.models import (
    Appointment,
    AppointmentStatus,
    BookingSource,
    Doctor,
    Hospital,
    Patient,
    Schedule,
)


def next_weekday(iso_weekday: int, weeks_ahead: int = 1) -> date:
    today = date.today()
    days = (iso_weekday - today.isoweekday()) % 7 + 7 * weeks_ahead
    return today + timedelta(days=days)


async def make_hospital(db: AsyncSession, **kw: Any) -> Hospital:
    fields: dict[str, Any] = {
        "name": "City Hospital",
        "address": "1 MG Road, Jabalpur",
        "phone": "+917612000000",
        "opening_time": time(8),
        "closing_time": time(20),
        "timezone": "Asia/Kolkata",
        "languages": ["en", "hi"],
    }
    fields.update(kw)
    hospital = Hospital(**fields)
    db.add(hospital)
    await db.commit()
    return hospital


async def make_doctor(db: AsyncSession, hospital: Hospital, **kw: Any) -> Doctor:
    fields: dict[str, Any] = {
        "hospital_id": hospital.id,
        "name": "Dr. Sharma",
        "speciality": "Cardiology",
        "department": "Cardiology",
        "max_daily_appointments": 20,
        "slot_duration_minutes": 30,
        "available_days": [1, 2, 3, 4, 5],
        "slot_start_time": time(9),
        "slot_end_time": time(12),
    }
    fields.update(kw)
    doctor = Doctor(**fields)
    db.add(doctor)
    await db.commit()
    return doctor


async def make_override(db: AsyncSession, doctor: Doctor, on: date, **kw: Any) -> Schedule:
    override = Schedule(doctor_id=doctor.id, date=on, **kw)
    db.add(override)
    await db.commit()
    return override


async def make_patient(
    db: AsyncSession, hospital: Hospital, name: str = "Rahul Kumar", phone: str = "+919876543210"
) -> Patient:
    patient = Patient(
        hospital_id=hospital.id, name=name, normalized_name=normalize_name(name), phone=phone
    )
    db.add(patient)
    await db.commit()
    return patient


async def make_appointment(
    db: AsyncSession,
    doctor: Doctor,
    patient: Patient,
    on: date,
    at: time,
    status: AppointmentStatus = AppointmentStatus.BOOKED,
    token: int | None = None,
) -> Appointment:
    if token is None:
        token = int(at.hour * 100 + at.minute)
    appt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        hospital_id=doctor.hospital_id,
        appointment_date=on,
        appointment_time=at,
        slot_duration_minutes=doctor.slot_duration_minutes,
        status=status,
        booking_source=BookingSource.DASHBOARD,
        token_number=token,
    )
    db.add(appt)
    await db.commit()
    return appt
