import hmac
from typing import Annotated, Any

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.security import decode_access_token
from app.database import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]

bearer_scheme = HTTPBearer(auto_error=False)
BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _staff_from(credentials: HTTPAuthorizationCredentials | None) -> dict[str, Any]:
    settings = get_settings()
    if not settings.auth_enabled:
        return {"sub": settings.admin_email, "role": "Hospital Staff", "name": settings.admin_name}
    if not credentials:
        raise _unauthorized("Missing authentication token")
    try:
        return decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise _unauthorized(f"Invalid authentication token: {exc}") from exc
    except RuntimeError as exc:  # server misconfiguration: never accept anything
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Authentication unavailable"
        ) from exc


async def require_staff(credentials: BearerCredentials = None) -> dict[str, Any]:
    """Authentication for every protected /api/v1 route (Part 5 - Task 5.3).

    Requires a valid staff JWT (Authorization: Bearer ...) and returns its payload,
    or raises 401.
    """
    return _staff_from(credentials)


async def require_staff_or_service(credentials: BearerCredentials = None) -> dict[str, Any]:
    """Like require_staff, but also accepts the telephony service key.

    Used on the /calls routes only, which the call pipeline writes to. The key is
    compared in constant time and grants nothing outside those routes.
    """
    key = get_settings().service_api_key
    if (
        key
        and credentials
        and hmac.compare_digest(credentials.credentials.encode("utf-8"), key.encode("utf-8"))
    ):
        return {"sub": "service:telephony", "role": "Service", "name": "Telephony service"}
    return _staff_from(credentials)


class PageParams(BaseModel):
    limit: int = 50
    offset: int = 0


def page_params(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PageParams:
    return PageParams(limit=limit, offset=offset)


Paging = Annotated[PageParams, Depends(page_params)]
