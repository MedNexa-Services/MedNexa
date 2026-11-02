import pytest

from agent.replies import done_reply

BOOKED = {
    "patient_name": "Rohan Mehta",
    "doctor_name": "Dr. Suresh Patel",
    "date": "2026-11-03",
    "weekday": "Tuesday",
    "time": "09:50",
    "token_number": 8,
}


def test_a_booking_gives_the_doctor_time_and_token_number() -> None:
    text = done_reply("book", BOOKED, "en")
    assert text.startswith("All set! Your appointment is booked with Dr. Suresh Patel on ")
    assert "Tuesday, 3 November at 9:50 AM" in text
    assert "Your token number is 8." in text
    assert text.endswith("Is there anything else I can help you with?")


def test_a_cancellation_names_the_patient_and_slot() -> None:
    text = done_reply("cancel", BOOKED, "en")
    assert "cancelled Rohan Mehta's appointment with Dr. Suresh Patel" in text
    assert "Tuesday, 3 November at 9:50 AM" in text


def test_a_reschedule_gives_the_new_slot_and_token() -> None:
    text = done_reply("reschedule", {**BOOKED, "time": "14:30"}, "en")
    assert "is now on Tuesday, 3 November at 2:30 PM" in text
    assert "token number is 8" in text


def test_hindi() -> None:
    text = done_reply("book", BOOKED, "hi")
    assert "Dr. Suresh Patel" in text and "3 नवंबर, 9:50 AM" in text and "टोकन नंबर 8" in text
    assert "All set" not in text


@pytest.mark.parametrize("time", ["09:50", "9:50", "09:50:00"])
def test_time_formats(time: str) -> None:
    assert "9:50 AM" in done_reply("book", {**BOOKED, "time": time}, "en")


@pytest.mark.parametrize("kind", ["book", "cancel", "reschedule"])
@pytest.mark.parametrize("language", ["en", "hi"])
def test_every_kind_in_every_language(kind: str, language: str) -> None:
    assert done_reply(kind, BOOKED, language)
