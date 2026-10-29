from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_staff
from app.config import get_settings
from app.core.security import create_access_token, verify_password
from app.schemas.auth import LoginRequest, StaffUserOut, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest) -> TokenResponse:
    """Authenticate hospital staff and issue an access JWT token."""
    settings = get_settings()

    # Verify admin/staff credentials
    if credentials.email.lower() != settings.admin_email.lower() or not verify_password(
        credentials.password, settings.admin_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires_minutes = settings.jwt_access_token_expire_minutes
    user_out = StaffUserOut(
        email=credentials.email,
        name="Dr. Admin",
        role="Hospital Staff",
    )
    token = create_access_token(
        data={"sub": credentials.email, "role": user_out.role, "name": user_out.name},
        expires_delta=timedelta(minutes=expires_minutes),
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_minutes * 60,
        user=user_out,
    )


@router.get("/me", response_model=StaffUserOut)
async def get_current_user(current_user: dict[str, Any] = Depends(require_staff)) -> StaffUserOut:
    """Return the profile of the currently authenticated staff member."""
    return StaffUserOut(
        email=str(current_user.get("sub", "")),
        name=str(current_user.get("name", "Staff Member")),
        role=str(current_user.get("role", "Hospital Staff")),
    )
