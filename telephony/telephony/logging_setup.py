from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

from telephony.config import get_settings

_PHONE_FIELDS = {"caller", "caller_phone", "phone"}
_TEXT_FIELDS = {"text", "response"}
_PHONE_NUMBER = re.compile(r"\+?\d(?:[ -]?\d){6,}")


def mask_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return "*" * max(0, len(digits) - 4) + digits[-4:] if len(digits) > 4 else value


def redact_phone_numbers(
    _: Any, __: str, event: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    for key, value in event.items():
        if not isinstance(value, str):
            continue
        if key in _PHONE_FIELDS:
            event[key] = mask_phone(value)
        elif key in _TEXT_FIELDS:
            event[key] = _PHONE_NUMBER.sub(lambda m: mask_phone(m.group()), value)
    return event


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            redact_phone_numbers,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "telephony") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
