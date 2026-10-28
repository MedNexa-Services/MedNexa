import pytest

from agent.language import detect_language, normalize_language


@pytest.mark.parametrize(
    "text, hint, expected",
    [
        ("मुझे कल डॉक्टर से मिलना है", None, "hi"),
        ("mujhe kal doctor se milna hai", "en", "hi"),  # Hinglish
        ("Kya aaj OPD khula hai?", None, "hi"),
        ("I want to book an appointment tomorrow", "hi", "en"),  # plain English beats a hint
        ("Dr. Sharma", "hi", "hi"),  # too short to tell: trust STT
        ("ok", None, "en"),
        ("", "hi", "hi"),
        ("haan ji", "en", "hi"),
    ],
)
def test_detect_language(text: str, hint: str | None, expected: str) -> None:
    assert detect_language(text, hint) == expected


@pytest.mark.parametrize(
    "code, expected", [("ur", "hi"), ("HI", "hi"), ("en", "en"), ("fr", None), (None, None)]
)
def test_normalize_language(code: str | None, expected: str | None) -> None:
    assert normalize_language(code) == expected
