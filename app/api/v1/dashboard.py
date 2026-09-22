from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import SingleResponse
from app.schemas.dashboard import DashboardSummaryOut
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=SingleResponse[DashboardSummaryOut])
def get_dashboard_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns real database counts and metrics for the organization."""
    summary = DashboardService.get_summary(db, current_user.organization_id)
    return SingleResponse(data=summary)
