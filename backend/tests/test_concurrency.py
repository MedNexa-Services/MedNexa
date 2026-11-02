import asyncio
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.exceptions import DailyCapReached, DomainError, SlotUnavailable
from app.models import Appointment, AppointmentStatus
from app.schemas.appointment import BookingRequest
from app.schemas.patient import PatientIn
from app.services.appointment_service import book_appointment, reschedule_appointment
from tests.factories import make_doctor, make_hospital, next_weekday

MONDAY = next_weekday(1)
NOW = datetime.combine(MONDAY - timedelta(days=3), time(8), ZoneInfo("Asia/Kolkata"))
PARALLEL = 20


async def _attempt(session_factory, req: BookingRequest):
    async with session_factory() as session:
        try:
            return await book_appointment(session, req, now=NOW)
        except DomainError as exc:
            return exc


def _req(doctor_id, at: time, i: int) -> BookingRequest:
    return BookingRequest(
        patient=PatientIn(name=f"Patient {i}", phone=f"+9198765{i:05d}"),
        doctor_id=doctor_id,
        appointment_date=MONDAY,
        appointment_time=at,
    )


async def test_parallel_bookings_for_last_slot_only_one_wins(db, session_factory) -> None:
    hospital = await make_hospital(db)
    doctor = await make_doctor(db, hospital, slot_start_time=time(9), slot_end_time=time(9, 30))

    results = await asyncio.gather(
        *(_attempt(session_factory, _req(doctor.id, time(9), i)) for i in range(PARALLEL))
    )

    wins = [r for r in results if not isinstance(r, Exception)]
    losses = [r for r in results if isinstance(r, Exception)]
    assert len(wins) == 1
    assert len(losses) == PARALLEL - 1
    assert all(isinstance(r, SlotUnavailable) for r in losses)

    booked = list(
        await db.scalars(select(Appointment).where(Appointment.status == AppointmentStatus.BOOKED))
    )
    assert len(booked) == 1


async def test_parallel_bookings_respect_daily_cap(db, session_factory) -> None:
    hospital = await make_hospital(db)
    doctor = await make_doctor(
        db, hospital, max_daily_appointments=3, slot_duration_minutes=10, slot_end_time=time(12)
    )
    slots = [time(9, 10 * (i % 6)) if i < 6 else time(10, 10 * (i % 6)) for i in range(12)]

    results = await asyncio.gather(
        *(_attempt(session_factory, _req(doctor.id, at, i)) for i, at in enumerate(slots))
    )

    wins = [r for r in results if not isinstance(r, Exception)]
    assert len(wins) == 3
    assert all(isinstance(r, DailyCapReached) for r in results if isinstance(r, Exception))
    assert sorted(w.token_number for w in wins) == [1, 2, 3]


async def test_parallel_bookings_get_unique_sequential_tokens(db, session_factory) -> None:
    hospital = await make_hospital(db)
    doctor = await make_doctor(db, hospital, slot_duration_minutes=10, slot_end_time=time(12))
    slots = [time(9 + i // 6, 10 * (i % 6)) for i in range(15)]

    results = await asyncio.gather(
        *(_attempt(session_factory, _req(doctor.id, at, i)) for i, at in enumerate(slots))
    )

    assert sorted(r.token_number for r in results) == list(range(1, 16))


async def test_reschedule_races_new_booking_for_same_slot(db, session_factory) -> None:
    hospital = await make_hospital(db)
    doctor = await make_doctor(db, hospital)
    original = await _attempt(session_factory, _req(doctor.id, time(9), 0))

    async def move():
        async with session_factory() as session:
            try:
                return await reschedule_appointment(
                    session, original.appointment_id, "+919876500000", MONDAY, time(10), now=NOW
                )
            except DomainError as exc:
                return exc

    results = await asyncio.gather(
        move(), *(_attempt(session_factory, _req(doctor.id, time(10), i)) for i in range(1, 10))
    )

    assert sum(not isinstance(r, Exception) for r in results) == 1
    at_ten = list(
        await db.scalars(
            select(Appointment).where(
                Appointment.appointment_time == time(10),
                Appointment.status == AppointmentStatus.BOOKED,
            )
        )
    )
    assert len(at_ten) == 1
