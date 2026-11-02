import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from app.core.exceptions import (
    DailyCapReached,
    DomainValidationError,
    DuplicateBooking,
    InvalidSlot,
    NotCancellable,
    NotFound,
    NotOwner,
    SlotUnavailable,
)
from app.models import Appointment, AppointmentStatus, BookingSource, Patient
from app.schemas.appointment import BookingRequest
from app.schemas.patient import PatientIn
from app.services.appointment_service import (
    book_appointment,
    cancel_appointment,
    cancel_appointment_by_staff,
    get_patient_appointments,
    reschedule_appointment,
    reschedule_appointment_by_staff,
)
from tests.factories import make_doctor, make_hospital, make_override, next_weekday

IST = ZoneInfo("Asia/Kolkata")
MONDAY = next_weekday(1)
NOW = datetime.combine(MONDAY - timedelta(days=3), time(8), IST)
PHONE = "+919876543210"


def booking(doctor_id: uuid.UUID, at: time, name: str = "Rahul Kumar", on: date = MONDAY, **kw):
    patient = PatientIn(name=name, phone=kw.pop("phone", PHONE), **kw.pop("patient", {}))
    return BookingRequest(
        patient=patient, doctor_id=doctor_id, appointment_date=on, appointment_time=at, **kw
    )


@pytest.fixture
async def hospital(db):
    return await make_hospital(db)


@pytest.fixture
async def doctor(db, hospital):
    return await make_doctor(db, hospital)


async def test_booking_returns_confirmation_with_token(db, doctor) -> None:
    conf = await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    assert conf.token_number == 1
    assert conf.doctor_name == doctor.name
    assert conf.patient_name == "Rahul Kumar"
    assert conf.status == AppointmentStatus.BOOKED


async def test_tokens_increase_per_doctor_day_and_are_not_reused(db, doctor) -> None:
    first = await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    await cancel_appointment_by_staff(db, first.appointment_id)
    second = await book_appointment(db, booking(doctor.id, time(9), name="Priya"), now=NOW)
    other_day = await book_appointment(
        db, booking(doctor.id, time(9), on=MONDAY + timedelta(days=1)), now=NOW
    )
    assert second.token_number == 2
    assert other_day.token_number == 1


async def test_same_phone_different_names_are_different_patients(db, doctor) -> None:
    await book_appointment(db, booking(doctor.id, time(9), name="Rahul Kumar"), now=NOW)
    await book_appointment(db, booking(doctor.id, time(9, 30), name="Sita Kumar"), now=NOW)
    assert await db.scalar(select(func.count()).select_from(Patient)) == 2


async def test_same_phone_same_name_reuses_patient(db, doctor) -> None:
    await book_appointment(db, booking(doctor.id, time(9), name="Rahul Kumar"), now=NOW)
    await book_appointment(
        db,
        booking(
            doctor.id, time(10), name="  rahul   KUMAR ", phone="98765 43210", patient={"age": 34}
        ),
        now=NOW,
    )
    patients = list(await db.scalars(select(Patient)))
    assert len(patients) == 1
    assert patients[0].age == 34


async def test_same_patient_same_slot_is_duplicate(db, doctor) -> None:
    await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    with pytest.raises(DuplicateBooking):
        await book_appointment(db, booking(doctor.id, time(9)), now=NOW)


async def test_other_patient_same_slot_is_unavailable(db, doctor) -> None:
    await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    with pytest.raises(SlotUnavailable):
        await book_appointment(db, booking(doctor.id, time(9), name="Priya"), now=NOW)


async def test_same_patient_same_doctor_different_time_allowed(db, doctor) -> None:
    await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    await book_appointment(db, booking(doctor.id, time(10)), now=NOW)


async def test_same_patient_different_doctor_same_time_allowed(db, hospital, doctor) -> None:
    other = await make_doctor(db, hospital, name="Dr. Patel")
    await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    await book_appointment(db, booking(other.id, time(9)), now=NOW)


async def test_cancelled_slot_can_be_rebooked(db, doctor) -> None:
    conf = await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    await cancel_appointment(db, conf.appointment_id, PHONE, now=NOW)
    again = await book_appointment(db, booking(doctor.id, time(9), name="Priya"), now=NOW)
    assert again.status == AppointmentStatus.BOOKED


async def test_daily_cap_enforced(db, hospital) -> None:
    doctor = await make_doctor(db, hospital, max_daily_appointments=2)
    await book_appointment(db, booking(doctor.id, time(9), name="A"), now=NOW)
    await book_appointment(db, booking(doctor.id, time(9, 30), name="B"), now=NOW)
    with pytest.raises(DailyCapReached):
        await book_appointment(db, booking(doctor.id, time(10), name="C"), now=NOW)


@pytest.mark.parametrize(
    "on, at, message",
    [
        (MONDAY, time(9, 15), "not one of the doctor's appointment slots"),
        (MONDAY, time(13), "not one of the doctor's appointment slots"),
        (next_weekday(7), time(9), "not available on that date"),
        (MONDAY - timedelta(days=7), time(9), "already passed"),
    ],
)
async def test_invalid_slots_rejected(db, doctor, on, at, message) -> None:
    with pytest.raises(InvalidSlot, match=message):
        await book_appointment(db, booking(doctor.id, at, on=on), now=NOW)


async def test_slot_that_already_started_today_rejected(db, doctor) -> None:
    now = datetime.combine(MONDAY, time(9, 10), IST)
    with pytest.raises(InvalidSlot, match="already passed"):
        await book_appointment(db, booking(doctor.id, time(9)), now=now)


async def test_override_day_off_rejected(db, doctor) -> None:
    await make_override(db, doctor, MONDAY, is_available=False)
    with pytest.raises(InvalidSlot, match="not available"):
        await book_appointment(db, booking(doctor.id, time(9)), now=NOW)


async def test_inactive_doctor_rejected(db, hospital) -> None:
    doctor = await make_doctor(db, hospital, is_active=False)
    with pytest.raises(DomainValidationError):
        await book_appointment(db, booking(doctor.id, time(9)), now=NOW)


async def test_unknown_doctor_rejected(db) -> None:
    with pytest.raises(NotFound):
        await book_appointment(db, booking(uuid.uuid4(), time(9)), now=NOW)


async def test_failed_booking_leaves_no_patient_behind(db, doctor) -> None:
    with pytest.raises(InvalidSlot):
        await book_appointment(db, booking(doctor.id, time(9, 15), name="Ghost"), now=NOW)
    assert await db.scalar(select(func.count()).select_from(Patient)) == 0


async def test_cancel_requires_matching_phone(db, doctor) -> None:
    conf = await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    with pytest.raises(NotOwner):
        await cancel_appointment(db, conf.appointment_id, "+919999999999", now=NOW)


async def test_cancel_accepts_differently_formatted_phone(db, doctor) -> None:
    conf = await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    out = await cancel_appointment(db, conf.appointment_id, "098765 43210", "fever gone", now=NOW)
    assert out.status == AppointmentStatus.CANCELLED
    assert out.cancellation_reason == "fever gone"
    assert out.cancelled_at is not None


async def test_cannot_cancel_twice(db, doctor) -> None:
    conf = await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    await cancel_appointment(db, conf.appointment_id, PHONE, now=NOW)
    with pytest.raises(NotCancellable):
        await cancel_appointment(db, conf.appointment_id, PHONE, now=NOW)


async def test_caller_cannot_cancel_past_appointment_but_staff_can(db, doctor) -> None:
    conf = await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    later = datetime.combine(MONDAY, time(10), IST)
    with pytest.raises(NotCancellable, match="passed"):
        await cancel_appointment(db, conf.appointment_id, PHONE, now=later)
    out = await cancel_appointment_by_staff(db, conf.appointment_id)
    assert out.status == AppointmentStatus.CANCELLED


async def test_cancel_unknown_appointment(db) -> None:
    with pytest.raises(NotFound):
        await cancel_appointment(db, uuid.uuid4(), PHONE)


async def test_reschedule_moves_booking_and_links_rows(db, doctor) -> None:
    conf = await book_appointment(db, booking(doctor.id, time(9), notes="BP check"), now=NOW)
    new = await reschedule_appointment(db, conf.appointment_id, PHONE, MONDAY, time(10), now=NOW)

    old_row = await db.get(Appointment, conf.appointment_id, populate_existing=True)
    new_row = await db.get(Appointment, new.appointment_id)
    assert old_row.status == AppointmentStatus.RESCHEDULED
    assert new_row.rescheduled_from_id == old_row.id
    assert new_row.notes == "BP check"
    assert new.token_number == 2


async def test_reschedule_frees_old_slot_for_cap(db, hospital) -> None:
    doctor = await make_doctor(db, hospital, max_daily_appointments=1)
    conf = await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    new = await reschedule_appointment(db, conf.appointment_id, PHONE, MONDAY, time(10), now=NOW)
    assert new.appointment_time == time(10)


async def test_reschedule_to_taken_slot_keeps_original(db, doctor) -> None:
    conf = await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    await book_appointment(db, booking(doctor.id, time(10), name="Priya"), now=NOW)
    with pytest.raises(SlotUnavailable):
        await reschedule_appointment(db, conf.appointment_id, PHONE, MONDAY, time(10), now=NOW)
    row = await db.get(Appointment, conf.appointment_id, populate_existing=True)
    assert row.status == AppointmentStatus.BOOKED


async def test_reschedule_to_same_slot_rejected(db, doctor) -> None:
    conf = await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    with pytest.raises(InvalidSlot, match="same"):
        await reschedule_appointment(db, conf.appointment_id, PHONE, MONDAY, time(9), now=NOW)


async def test_reschedule_requires_owner(db, doctor) -> None:
    conf = await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    with pytest.raises(NotOwner):
        await reschedule_appointment(
            db, conf.appointment_id, "+919999999999", MONDAY, time(10), now=NOW
        )


async def test_staff_reschedule(db, doctor) -> None:
    conf = await book_appointment(
        db, booking(doctor.id, time(9), booking_source=BookingSource.DASHBOARD), now=NOW
    )
    new = await reschedule_appointment_by_staff(
        db, conf.appointment_id, MONDAY + timedelta(days=1), time(9)
    )
    row = await db.get(Appointment, new.appointment_id)
    assert row.booking_source == BookingSource.DASHBOARD


async def test_get_patient_appointments_requires_name_and_phone(db, doctor) -> None:
    await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    await book_appointment(db, booking(doctor.id, time(9, 30), name="Sita Kumar"), now=NOW)

    mine = await get_patient_appointments(
        db, doctor.hospital_id, "9876543210", "rahul kumar", now=NOW
    )
    assert [a.appointment_time for a in mine] == [time(9)]
    assert await get_patient_appointments(db, doctor.hospital_id, PHONE, "Nobody", now=NOW) == []
    assert await get_patient_appointments(db, doctor.hospital_id, "bad", "Rahul", now=NOW) == []


async def test_a_misheard_name_still_finds_the_callers_own_booking(db, doctor) -> None:
    await book_appointment(db, booking(doctor.id, time(9), name="Asha"), now=NOW)
    await book_appointment(db, booking(doctor.id, time(9, 30), name="Rohan Mehta"), now=NOW)
    hid = doctor.hospital_id

    for heard in ("Aasha", "asha ", "Rohan"):
        found = await get_patient_appointments(db, hid, PHONE, heard, now=NOW)
        assert len(found) == 1, heard
    assert await get_patient_appointments(db, hid, PHONE, "Ershah", now=NOW) == []
    other = "+919123456789"
    assert await get_patient_appointments(db, hid, other, "Asha", now=NOW) == []


async def test_an_ambiguous_misheard_name_matches_nothing(db, doctor) -> None:
    await book_appointment(db, booking(doctor.id, time(9), name="Asha Rao"), now=NOW)
    await book_appointment(db, booking(doctor.id, time(9, 30), name="Asha Rai"), now=NOW)
    assert await get_patient_appointments(db, doctor.hospital_id, PHONE, "Asha", now=NOW) == []


async def test_get_patient_appointments_upcoming_only(db, doctor) -> None:
    await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    after = datetime.combine(MONDAY + timedelta(days=1), time(8), IST)
    hid = doctor.hospital_id
    assert await get_patient_appointments(db, hid, PHONE, "Rahul Kumar", now=after) == []
    history = await get_patient_appointments(
        db, hid, PHONE, "Rahul Kumar", upcoming_only=False, now=after
    )
    assert len(history) == 1


async def test_upcoming_appointments_exclude_cancelled_rescheduled_and_past(db, doctor) -> None:
    cancelled = await book_appointment(db, booking(doctor.id, time(9)), now=NOW)
    await cancel_appointment(db, cancelled.appointment_id, PHONE, now=NOW)
    moved = await book_appointment(db, booking(doctor.id, time(9, 30)), now=NOW)
    await reschedule_appointment(db, moved.appointment_id, PHONE, MONDAY, time(11), now=NOW)
    await book_appointment(db, booking(doctor.id, time(10)), now=NOW)

    during_monday = datetime.combine(MONDAY, time(10, 15), IST)
    upcoming = await get_patient_appointments(
        db, doctor.hospital_id, PHONE, "Rahul Kumar", now=during_monday
    )
    assert [(a.appointment_time, a.status) for a in upcoming] == [
        (time(11), AppointmentStatus.BOOKED)
    ]

    history = await get_patient_appointments(
        db, doctor.hospital_id, PHONE, "Rahul Kumar", upcoming_only=False, now=during_monday
    )
    assert len(history) == 4
