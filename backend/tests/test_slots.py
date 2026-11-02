import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.core.exceptions import NotFound
from app.models import AppointmentStatus, Doctor, Schedule
from app.services import slot_service
from app.services.slot_service import find_next_available, get_available_slots, plan_day
from tests.factories import (
    make_appointment,
    make_doctor,
    make_hospital,
    make_override,
    make_patient,
    next_weekday,
)

IST = ZoneInfo("Asia/Kolkata")
MONDAY = next_weekday(1)
SUNDAY = next_weekday(7)


def _doctor(**kw: object) -> Doctor:
    fields: dict[str, object] = {
        "max_daily_appointments": 20,
        "slot_duration_minutes": 30,
        "available_days": [1, 2, 3, 4, 5],
        "slot_start_time": time(9),
        "slot_end_time": time(11),
    }
    fields.update(kw)
    return Doctor(**fields)


def _at(d: date, t: time) -> datetime:
    return datetime.combine(d, t, IST)


EARLY = _at(MONDAY - timedelta(days=3), time(8))


def test_template_day_gives_full_grid() -> None:
    plan = plan_day(_doctor(), MONDAY, None, {}, EARLY)
    assert plan.free_slots() == [time(9), time(9, 30), time(10), time(10, 30)]


def test_non_working_day_has_no_slots() -> None:
    assert plan_day(_doctor(), SUNDAY, None, {}, EARLY).free_slots() == []


def test_override_day_off() -> None:
    off = Schedule(date=MONDAY, is_available=False)
    assert plan_day(_doctor(), MONDAY, off, {}, EARLY).free_slots() == []


def test_override_makes_non_working_day_available() -> None:
    extra = Schedule(date=SUNDAY, is_available=True, start_time=time(10), end_time=time(11))
    assert plan_day(_doctor(), SUNDAY, extra, {}, EARLY).free_slots() == [time(10), time(10, 30)]


def test_partial_override_falls_back_to_template_times() -> None:
    late_start = Schedule(date=MONDAY, is_available=True, start_time=time(10), end_time=None)
    assert plan_day(_doctor(), MONDAY, late_start, {}, EARLY).free_slots() == [
        time(10),
        time(10, 30),
    ]


def test_slot_must_fit_before_end_of_window() -> None:
    doctor = _doctor(slot_duration_minutes=45)
    assert plan_day(doctor, MONDAY, None, {}, EARLY).free_slots() == [time(9), time(9, 45)]


def test_booked_slots_are_removed() -> None:
    booked = {time(9, 30): uuid.uuid4()}
    assert time(9, 30) not in plan_day(_doctor(), MONDAY, None, booked, EARLY).free_slots()


def test_daily_cap_blocks_whole_day() -> None:
    booked = {time(9): uuid.uuid4(), time(9, 30): uuid.uuid4()}
    plan = plan_day(_doctor(max_daily_appointments=2), MONDAY, None, booked, EARLY)
    assert plan.cap_reached
    assert plan.free_slots() == []


def test_today_hides_slots_that_already_started() -> None:
    now = _at(MONDAY, time(9, 30))
    assert plan_day(_doctor(), MONDAY, None, {}, now).free_slots() == [time(10), time(10, 30)]


def test_past_date_has_no_slots() -> None:
    now = _at(MONDAY + timedelta(days=1), time(8))
    assert plan_day(_doctor(), MONDAY, None, {}, now).free_slots() == []


async def test_cancelled_appointment_frees_the_slot(db) -> None:
    hospital = await make_hospital(db)
    doctor = await make_doctor(db, hospital, slot_end_time=time(10))
    patient = await make_patient(db, hospital)
    await make_appointment(db, doctor, patient, MONDAY, time(9), status=AppointmentStatus.CANCELLED)
    await make_appointment(db, doctor, patient, MONDAY, time(9, 30))

    slots = await get_available_slots(db, doctor.id, MONDAY, now=EARLY)
    assert [s.start for s in slots] == [time(9)]
    assert slots[0].end == time(9, 30)


async def test_override_row_is_applied(db) -> None:
    hospital = await make_hospital(db)
    doctor = await make_doctor(db, hospital)
    await make_override(db, doctor, MONDAY, is_available=False, override_reason="Conference")
    assert await get_available_slots(db, doctor.id, MONDAY, now=EARLY) == []


async def test_inactive_doctor_has_no_slots(db) -> None:
    hospital = await make_hospital(db)
    doctor = await make_doctor(db, hospital, is_active=False)
    assert await get_available_slots(db, doctor.id, MONDAY, now=EARLY) == []


async def test_unknown_doctor_raises(db) -> None:
    with pytest.raises(NotFound):
        await get_available_slots(db, uuid.uuid4(), MONDAY)


async def test_default_now_uses_hospital_timezone(db, monkeypatch) -> None:
    hospital = await make_hospital(db, timezone="Asia/Kolkata")
    doctor = await make_doctor(db, hospital)
    seen: list[str] = []

    def fake_now(tz: str) -> datetime:
        seen.append(tz)
        return EARLY

    monkeypatch.setattr(slot_service, "hospital_now", fake_now)
    await get_available_slots(db, doctor.id, MONDAY)
    assert seen == ["Asia/Kolkata"]


async def test_find_next_available_orders_and_limits(db) -> None:
    hospital = await make_hospital(db)
    a = await make_doctor(db, hospital, name="Dr. A", slot_start_time=time(10))
    b = await make_doctor(db, hospital, name="Dr. B", slot_start_time=time(9))
    await make_doctor(db, hospital, name="Dr. Skin", speciality="Dermatology", department="Skin")

    results = await find_next_available(db, hospital.id, "cardio", MONDAY, limit=3, now=EARLY)
    assert [(r.doctor_name, r.date, r.start) for r in results] == [
        ("Dr. B", MONDAY, time(9)),
        ("Dr. B", MONDAY, time(9, 30)),
        ("Dr. A", MONDAY, time(10)),
    ]
    assert {r.doctor_id for r in results} == {a.id, b.id}


async def test_find_next_available_skips_full_days(db) -> None:
    hospital = await make_hospital(db)
    doctor = await make_doctor(db, hospital, max_daily_appointments=1)
    patient = await make_patient(db, hospital)
    await make_appointment(db, doctor, patient, MONDAY, time(9))

    results = await find_next_available(db, hospital.id, "Cardiology", MONDAY, limit=1, now=EARLY)
    assert results[0].date == MONDAY + timedelta(days=1)


async def test_find_next_available_never_returns_past_dates(db) -> None:
    hospital = await make_hospital(db)
    await make_doctor(db, hospital)
    now = _at(MONDAY, time(8))
    results = await find_next_available(
        db, hospital.id, "Cardiology", MONDAY - timedelta(days=7), limit=1, now=now
    )
    assert results[0].date == MONDAY


async def test_find_next_available_horizon_is_exactly_14_days(db) -> None:
    hospital = await make_hospital(db)
    doctor = await make_doctor(db, hospital, available_days=[1], max_daily_appointments=1)
    patient = await make_patient(db, hospital)
    await make_appointment(db, doctor, patient, MONDAY, time(9))
    await make_override(db, doctor, MONDAY + timedelta(days=7), is_available=False)

    assert await find_next_available(db, hospital.id, "Cardiology", MONDAY, now=EARLY) == []
