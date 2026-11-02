"""Map domain exceptions to HTTP responses.

Error body: {"error": {"code": "<stable code>", "message": "<human readable>"}}
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.core import exceptions as exc

logger = logging.getLogger(__name__)

STATUS_BY_ERROR: dict[type[exc.DomainError], int] = {
    exc.NotFound: status.HTTP_404_NOT_FOUND,
    exc.NotOwner: status.HTTP_403_FORBIDDEN,
    exc.DomainValidationError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    exc.InvalidSlot: status.HTTP_422_UNPROCESSABLE_CONTENT,
    exc.SlotUnavailable: status.HTTP_409_CONFLICT,
    exc.DailyCapReached: status.HTTP_409_CONFLICT,
    exc.DuplicateBooking: status.HTTP_409_CONFLICT,
    exc.NotCancellable: status.HTTP_409_CONFLICT,
    exc.Conflict: status.HTTP_409_CONFLICT,
}


def _body(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


async def _domain_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, exc.DomainError)
    status_code = next(
        (code for cls, code in STATUS_BY_ERROR.items() if isinstance(error, cls)),
        status.HTTP_400_BAD_REQUEST,
    )
    return JSONResponse(_body(error.code, error.message), status_code=status_code)


async def _integrity_error(_: Request, error: Exception) -> JSONResponse:
    logger.warning("Unhandled integrity error: %s", error)
    return JSONResponse(
        _body("conflict", "The request conflicts with existing data"),
        status_code=status.HTTP_409_CONFLICT,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(exc.DomainError, _domain_error)
    app.add_exception_handler(IntegrityError, _integrity_error)
