from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.control_plane.system import (
    DatabaseHealthResponse,
    ReadinessResponse,
    SystemHealthResponse,
)
from app.services.control_plane.health_service import HealthService

router = APIRouter(prefix="/system", tags=["System & Health"])


@router.get("/health", response_model=SystemHealthResponse)
def get_system_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns aggregated deterministic system health status across all components."""
    return HealthService.get_system_health(db)


@router.get("/readiness", response_model=ReadinessResponse)
def get_system_readiness(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verifies production readiness of required infrastructure dependencies."""
    return HealthService.get_readiness(db)


@router.get("/database", response_model=DatabaseHealthResponse)
def get_database_health(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns real-time database connection metrics and health."""
    return HealthService.get_database_health(db)

