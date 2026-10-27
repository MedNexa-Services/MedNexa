from agent.events import CallEvent, CallEvents

BOOK = {
    "patient_name": "Rahul Kumar",
    "doctor_name": "Dr. Sharma",
    "date": "2026-11-02",
    "time": "09:00",
    "token_number": 1,
}


def log(*items: CallEvent) -> CallEvents:
    events = CallEvents()
    for item in items:
        events.add(item)
    return events


def test_outcome_priority() -> None:
    info = CallEvent("get_hospital_info", "info", True, {})
    booked = CallEvent("book_appointment", "book", True, BOOK)
    escalate = CallEvent("transfer_to_human", "escalate", True, {"reason": "asked"})
    assert log().outcome() == "OTHER"
    assert log(info).outcome() == "INFO_PROVIDED"
    assert log(info, booked).outcome() == "BOOKED"
    assert log(booked, escalate).outcome() == "ESCALATED"


def test_failed_actions_do_not_count_as_outcome() -> None:
    failed = CallEvent("book_appointment", "book", False, {"error": "slot_unavailable"})
    assert log(failed).outcome() == "OTHER"


def test_summary_describes_actions() -> None:
    events = log(
        CallEvent("list_doctors", "info", True, {}),
        CallEvent("book_appointment", "book", False, {"error": "slot_unavailable"}),
        CallEvent("book_appointment", "book", True, BOOK),
        CallEvent("cancel_appointment", "cancel", True, {**BOOK, "time": "11:00"}),
    )
    summary = events.summary()
    assert summary is not None
    assert "Booked Rahul Kumar with Dr. Sharma on 2026-11-02 at 09:00 (token 1)." in summary
    assert "Cancelled Rahul Kumar's appointment" in summary
    assert "list_doctors" in summary
    assert "slot_unavailable" in summary


def test_empty_call_has_no_summary() -> None:
    assert log().summary() is None


def test_confirmed_tokens_include_looked_up_appointments() -> None:
    lookup = CallEvent(
        "get_my_appointments", "lookup", True, {"appointments": [{"token_number": 5}]}
    )
    assert log(lookup, CallEvent("book_appointment", "book", True, BOOK)).confirmed_tokens() == {
        1,
        5,
    }
