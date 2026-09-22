from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.db.models.user import User
from app.schemas.common import PaginatedResponse, SingleResponse
from app.schemas.telephony import (
    AiStatusSummaryOut,
    GatewayHeartbeat,
    TelephonyGatewayCreate,
    TelephonyGatewayOut,
    TelephonyStatusOut,
)
from app.services.telephony import TelephonyService

router = APIRouter(tags=["Telephony"])


@router.get("/telephony/status", response_model=SingleResponse[TelephonyStatusOut])
def get_telephony_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    status_data = TelephonyService.get_telephony_status(db, current_user.organization_id)
    return SingleResponse(data=status_data)


@router.get("/telephony/gateways", response_model=PaginatedResponse[TelephonyGatewayOut])
def list_gateways(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = TelephonyService.list_gateways(
        db=db,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(items=items, page=page, page_size=page_size, total=total)


@router.post("/telephony/gateways", response_model=SingleResponse[TelephonyGatewayOut], status_code=status.HTTP_201_CREATED)
def create_gateway(
    payload: TelephonyGatewayCreate,
    current_user: User = Depends(require_role("SUPERVISOR", "ORG_ADMIN")),
    db: Session = Depends(get_db),
):
    gw = TelephonyService.create_gateway(db, current_user.organization_id, payload)
    return SingleResponse(data=gw)


@router.get("/telephony/gateways/{gateway_id}", response_model=SingleResponse[TelephonyGatewayOut])
def get_gateway(
    gateway_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gw = TelephonyService.get_gateway(db, current_user.organization_id, gateway_id)
    return SingleResponse(data=gw)


@router.post("/telephony/gateways/{gateway_id}/heartbeat", response_model=SingleResponse[TelephonyGatewayOut])
def record_gateway_heartbeat(
    gateway_id: uuid.UUID,
    payload: GatewayHeartbeat,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gw = TelephonyService.record_heartbeat(db, current_user.organization_id, gateway_id, payload)
    return SingleResponse(data=gw)


@router.get("/ai/status", response_model=SingleResponse[AiStatusSummaryOut])
def get_ai_status(
    current_user: User = Depends(get_current_user),
):
    status_data = TelephonyService.get_ai_status()
    return SingleResponse(data=status_data)
