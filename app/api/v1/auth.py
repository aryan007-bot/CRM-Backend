from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.auth import LoginRequest, TokenResponse, UserOut
from app.schemas.common import SingleResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("auth:login", settings.LOGIN_RATE_LIMIT_PER_MINUTE))],
)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    """Authenticate user with email and password, returning JWT access token."""
    return AuthService.authenticate_user(db, data)


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """Logs out the current authenticated user."""
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=SingleResponse[UserOut])
def get_me(current_user: User = Depends(get_current_user)):
    """Returns details of the currently authenticated user."""
    user_out = UserOut(
        id=current_user.id,
        organization_id=current_user.organization_id,
        name=current_user.name,
        email=current_user.email,
        roles=current_user.roles,
        primary_role=current_user.primary_role,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
    return SingleResponse(data=user_out)
