import asyncio
import contextlib
import logging
import re
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.api.errors import register_error_handlers
from app.api.router import api_router
from app.config import get_settings
from app.database import SessionFactory
from app.services import call_service

logger = logging.getLogger(__name__)

_PHONE_QUERY = re.compile(r"((?:^|[?&])(?:caller_)?phone=)([^&]*)")


def _mask_digits(value: str) -> str:
    prefix = re.match(r"(?i)(%2B|\+)?", value).group()  # type: ignore[union-attr]
    return prefix + re.sub(r"\d(?=(?:\D*\d){4})", "*", value[len(prefix) :])


class MaskPhoneNumbersInAccessLog(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            path = _PHONE_QUERY.sub(lambda m: m.group(1) + _mask_digits(m.group(2)), args[2])
            record.args = (*args[:2], path, *args[3:])
        return True


logging.getLogger("uvicorn.access").addFilter(MaskPhoneNumbersInAccessLog())

_SAFE_CORRELATION_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = request.headers.get("X-Correlation-ID", "")
        correlation_id = supplied if _SAFE_CORRELATION_ID.fullmatch(supplied) else str(uuid.uuid4())
        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


async def purge_old_calls_daily(days: int) -> None:
    while True:
        try:
            async with SessionFactory() as db:
                deleted = await call_service.purge_calls_older_than(db, days)
            if deleted:
                logger.info("Deleted %d call sessions older than %d days", deleted, days)
        except Exception:
            logger.exception("Call-log purge failed; retrying in 24 hours")
        await asyncio.sleep(24 * 60 * 60)


async def close_stale_calls_hourly() -> None:
    while True:
        try:
            async with SessionFactory() as db:
                closed = await call_service.close_stale_calls(db)
            if closed:
                logger.info("Closed %d calls that were never ended", closed)
        except Exception:
            logger.exception("Closing stale calls failed; retrying in an hour")
        await asyncio.sleep(60 * 60)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    settings.require_auth_config()
    tasks = [asyncio.create_task(close_stale_calls_hourly())]
    if settings.call_log_retention_days > 0:
        tasks.append(asyncio.create_task(purge_old_calls_daily(settings.call_log_retention_days)))
    yield
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError):
            await task


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID"],
    )
    register_error_handlers(app)
    app.include_router(api_router)
    return app


app = create_app()
