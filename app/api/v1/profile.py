from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import SingleResponse
from app.schemas.profile import ProfileOut, ProfileUpdate
from app.services.auth import AuthService

router = APIRouter(prefix="/profile", tags=["Profile"])


@router.get("", response_model=SingleResponse[ProfileOut])
def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve profile of the current authenticated user."""
    profile = AuthService.get_profile(db, current_user.id)
    return SingleResponse(data=profile)


@router.patch("", response_model=SingleResponse[ProfileOut])
def update_profile(
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update profile attributes (name, email) without altering roles."""
    updated = AuthService.update_profile(db, current_user.id, data)
    return SingleResponse(data=updated)
