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

# A client-supplied id is only propagated if it is short and made of safe characters;
# anything else (control characters, huge values) is replaced, so it can't pollute logs.
_SAFE_CORRELATION_ID = re.compile(r"[A-Za-z0-9._-]{1,64}")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Injects or propagates X-Correlation-ID for distributed log tracing."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        supplied = request.headers.get("X-Correlation-ID", "")
        correlation_id = supplied if _SAFE_CORRELATION_ID.fullmatch(supplied) else str(uuid.uuid4())
        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id
        return response


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    get_settings().require_auth_config()  # refuse to start with unusable auth settings
    yield


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
