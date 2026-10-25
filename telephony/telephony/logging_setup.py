"""Structured logging setup for the telephony pipeline.

Uses structlog for JSON-formatted logs with per-call correlation IDs.
Import `get_logger` everywhere instead of the stdlib `logging` module.
"""

from __future__ import annotations

import logging
import sys

import structlog

from telephony.config import get_settings


def configure_logging() -> None:
    """Call once at startup (in main.py)."""
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
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "telephony") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
