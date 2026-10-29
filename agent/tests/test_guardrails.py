import pytest

from agent.events import CallEvent, CallEvents
from agent.guardrails import apply_guardrails


def events(*items: CallEvent) -> CallEvents:
    log = CallEvents()
    for item in items:
        log.add(item)
    return log


BOOKED = CallEvent("book_appointment", "book", True, {"token_number": 3})
CANCELLED = CallEvent("cancel_appointment", "cancel", True, {"token_number": 2})


def check(text: str, log: CallEvents | None = None, language: str = "en", max_chars: int = 600):
    return apply_guardrails(text, log or CallEvents(), language, max_chars=max_chars)


def test_clean_reply_passes_unchanged() -> None:
    result = check("Dr. Sharma is available on Monday at 10:30 AM. Shall I book it?")
    assert not result.changed
    assert result.text.startswith("Dr. Sharma")


def test_empty_reply_gets_fallback_in_callers_language() -> None:
    assert check("  ", language="hi").text.startswith("माफ़")
    assert check("").violations == ["empty"]


@pytest.mark.parametrize(
    "text",
    [
        "You can take paracetamol 500 mg twice a day.",
        "Try taking some painkillers until your appointment.",
        "I would recommend an antibiotic for that.",
        "You probably have a viral infection.",
        "आप यह दवा लें, आराम मिलेगा।",
    ],
)
def test_medical_advice_is_replaced(text: str) -> None:
    result = check(text)
    assert result.violations == ["medical_advice"]
    assert "can't give medical advice" in result.text


@pytest.mark.parametrize(
    "text",
    [
        "The pharmacy is open 24 hours and the doctor can see you at 10 AM.",
        "Please have your medicines list ready for the doctor.",
        "Do you have any medicine allergies the doctor should know about?",
        "Please bring your current medications to the appointment.",
    ],
)
def test_receptionist_phrases_are_not_mistaken_for_advice(text: str) -> None:
    assert not check(text).changed


@pytest.mark.parametrize(
    "text",
    [
        "Your appointment has been booked for Monday.",
        "I have booked Dr. Sharma for you.",
        "Your token number is 7.",
        "Your appointment has been cancelled.",
        "आपकी अपॉइंटमेंट बुक हो गई है।",
    ],
)
def test_claims_without_tool_success_are_blocked(text: str) -> None:
    assert check(text).violations == ["ungrounded_claim"]


def test_claims_backed_by_tool_results_pass() -> None:
    log = events(BOOKED, CANCELLED)
    assert not check("Your appointment has been booked. Your token number is 3.", log).changed
    assert not check("Your appointment has been cancelled.", log).changed


def test_wrong_token_number_is_blocked() -> None:
    assert check("Your token number is 4.", events(BOOKED)).violations == ["ungrounded_claim"]


def test_failed_booking_does_not_ground_a_claim() -> None:
    failed = CallEvent("book_appointment", "book", False, {"error": "slot_unavailable"})
    assert check("Your appointment is booked.", events(failed)).changed


def test_already_booked_slot_message_is_not_a_claim() -> None:
    assert not check("Sorry, that slot is already booked. 11 AM is free.").changed


def test_uuids_are_removed() -> None:
    result = check("Found appointment 0b7f1c2e-1d2a-4c3b-9a8e-1234567890ab with Dr. Rao.")
    assert result.violations == ["internal_id"]
    assert result.text == "Found appointment with Dr. Rao."


def test_long_reply_trimmed_at_sentence_boundary() -> None:
    text = "First sentence here. Second sentence is a bit longer. Third one."
    result = check(text, max_chars=40)
    assert result.text == "First sentence here."
    assert result.violations == ["too_long"]
