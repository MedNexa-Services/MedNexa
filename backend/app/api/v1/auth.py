import hmac
from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import require_staff
from app.config import get_settings
from app.core.rate_limit import FailedLoginLimiter
from app.core.security import create_access_token, verify_password
from app.schemas.auth import LoginRequest, StaffUserOut, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# 5 wrong passwords per account per 5 minutes; a looser per-address limit stops one
# machine from sweeping many accounts (and from locking everyone out behind a proxy).
EMAIL_LIMITER = FailedLoginLimiter(max_failures=5, window_seconds=300)
ADDRESS_LIMITER = FailedLoginLimiter(max_failures=30, window_seconds=300)


def _too_many(retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Too many failed sign-in attempts. Try again later.",
        headers={"Retry-After": str(retry_after)},
    )


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest, request: Request) -> TokenResponse:
    """Authenticate hospital staff and issue an access JWT."""
    settings = get_settings()
    if not (settings.admin_email and settings.admin_password):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Sign-in is not configured"
        )

    email = credentials.email.strip().lower()
    address = request.client.host if request.client else "unknown"
    blocked = max(EMAIL_LIMITER.retry_after(email), ADDRESS_LIMITER.retry_after(address))
    if blocked:
        raise _too_many(blocked)

    # Always evaluate both checks so timing doesn't reveal which one failed.
    email_ok = hmac.compare_digest(
        email.encode("utf-8"), settings.admin_email.strip().lower().encode("utf-8")
    )
    password_ok = verify_password(credentials.password, settings.admin_password)
    if not (email_ok and password_ok):
        EMAIL_LIMITER.record_failure(email)
        ADDRESS_LIMITER.record_failure(address)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    EMAIL_LIMITER.reset(email)
    expires_minutes = settings.jwt_access_token_expire_minutes
    user = StaffUserOut(email=settings.admin_email, name=settings.admin_name, role="Hospital Staff")
    token = create_access_token(
        data={"sub": user.email, "role": user.role, "name": user.name},
        expires_delta=timedelta(minutes=expires_minutes),
    )
    return TokenResponse(
        access_token=token, token_type="bearer", expires_in=expires_minutes * 60, user=user
    )


@router.get("/me", response_model=StaffUserOut)
async def get_current_user(current_user: dict[str, Any] = Depends(require_staff)) -> StaffUserOut:
    """Return the profile of the currently authenticated staff member."""
    return StaffUserOut(
        email=str(current_user.get("sub", "")),
        name=str(current_user.get("name", "Staff Member")),
        role=str(current_user.get("role", "Hospital Staff")),
    )
