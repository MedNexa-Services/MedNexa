import re

from app.config import get_settings

_NON_DIGITS = re.compile(r"\D")
_WHITESPACE = re.compile(r"\s+")


def normalize_phone(raw: str) -> str:
    raw = raw.strip()
    digits = _NON_DIGITS.sub("", raw)
    country = get_settings().default_country_code
    if raw.startswith("+"):
        result = digits
    elif len(digits) == 10:
        result = country + digits
    elif len(digits) == 11 and digits.startswith("0"):
        result = country + digits[1:]
    else:
        result = digits
    if not 8 <= len(result) <= 15:
        raise ValueError("invalid phone number")
    return "+" + result


def normalize_name(name: str) -> str:
    return _WHITESPACE.sub(" ", name).strip().casefold()


def clean_name(name: str) -> str:
    return _WHITESPACE.sub(" ", name).strip()
