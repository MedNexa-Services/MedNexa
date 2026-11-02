from __future__ import annotations

import pytest

from telephony.logging_setup import mask_phone, redact_phone_numbers


@pytest.mark.parametrize(
    ("number", "masked"),
    [("+919876543210", "********3210"), ("98765 43210", "******3210"), ("1234", "1234")],
)
def test_mask_phone_keeps_only_the_last_four_digits(number: str, masked: str) -> None:
    assert mask_phone(number) == masked


def test_caller_fields_are_masked() -> None:
    event = redact_phone_numbers(None, "info", {"event": "x", "caller": "+919876543210"})
    assert event["caller"] == "********3210"


def test_numbers_spoken_in_transcripts_are_masked() -> None:
    event = redact_phone_numbers(
        None,
        "info",
        {"text": "my number is 98765 43210, token 7", "response": "Booked for 10:30 AM"},
    )
    assert event["text"] == "my number is ******3210, token 7"
    assert event["response"] == "Booked for 10:30 AM"


def test_other_fields_are_left_alone() -> None:
    session_id = "123e4567-e89b-12d3-a456-426614174000"
    event = redact_phone_numbers(None, "info", {"session_id": session_id, "stt_ms": 1234567})
    assert event == {"session_id": session_id, "stt_ms": 1234567}
