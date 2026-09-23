import os
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.telephony.asterisk import AsteriskTelephonyAdapter
from app.api.v1.deps import get_current_user, get_db, require_role
from app.core.errors import NotFoundException, ValidationException
from app.db.models.telephony import TelephonyGateway
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

asterisk_adapter = AsteriskTelephonyAdapter()
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


class TestCallRequest(BaseModel):
    destination_phone: str
    caller_phone: Optional[str] = None
    mode: Optional[str] = "LIVE"


@router.get("/telephony/diagnostics")
def get_telephony_diagnostics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Authoritative telephony readiness diagnostics (Asterisk, Gateway, PJSIP, Route, GSM)."""
    ast_check = asterisk_adapter.health_check()
    gateway = db.execute(
        select(TelephonyGateway)
        .where(TelephonyGateway.organization_id == current_user.organization_id, TelephonyGateway.status == "ONLINE")
    ).scalar_one_or_none()

    gw_status = "REGISTERED" if gateway else "UNREGISTERED"
    route_status = "CONFIGURED" if (gateway or os.getenv("OUTBOUND_TRUNK")) else "NOT_CONFIGURED"
    is_ready = ast_check["status"] == "HEALTHY" and gw_status == "REGISTERED"

    return SingleResponse(
        data={
            "ready": is_ready,
            "asterisk": {
                "status": ast_check["status"],
                "endpoint": ast_check["ari_endpoint"],
                "active_channels": ast_check["active_channels"],
            },
            "gateway": {
                "status": gw_status,
                "name": gateway.name if gateway else None,
                "type": gateway.gateway_type if gateway else None,
                "active_channels": gateway.active_channels if gateway else 0,
            },
            "endpoint": {
                "status": "AVAILABLE" if (gateway or os.getenv("OUTBOUND_TRUNK")) else "UNAVAILABLE",
            },
            "outbound_route": {
                "status": route_status,
                "trunk": os.getenv("OUTBOUND_TRUNK", "gsm-gateway"),
                "context": os.getenv("OUTBOUND_CONTEXT", "ai-recovery"),
            },
            "gsm": {
                "status": "READY" if gateway and gateway.gateway_type == "GSM" else "NOT_CONFIGURED",
                "signal_strength": gateway.signal_strength if gateway else 0,
                "network_operator": gateway.network_operator if gateway else None,
            },
        }
    )


@router.post("/telephony/test-call", status_code=status.HTTP_201_CREATED)
async def originate_test_call(
    payload: TestCallRequest,
    current_user: User = Depends(require_role("SUPERVISOR", "ORG_ADMIN", "SUPER_ADMIN")),
    db: Session = Depends(get_db),
):
    """Admin-only diagnostic operation: originates a controlled test call through the telephony stack."""
    from app.db.models.customer import Customer, CustomerPhone
    from app.services.telephony_core.phone_number_service import PhoneNumberService
    from app.services.live_calls import LiveCallService
    from app.schemas.call import CallCreate

    valid, norm_phone, err = PhoneNumberService.normalize_phone(payload.destination_phone)
    if not valid:
        raise ValidationException(f"Invalid test phone: {err}")

    # Ensure a test customer exists for this org
    test_cust = db.execute(
        select(Customer).where(Customer.organization_id == current_user.organization_id, Customer.name == "Telephony Test Handset")
    ).scalar_one_or_none()

    if not test_cust:
        test_cust = Customer(
            organization_id=current_user.organization_id,
            name="Telephony Test Handset",
            email="test-handset@internal.local",
            status="active",
        )
        db.add(test_cust)
        db.flush()
        db.add(CustomerPhone(customer_id=test_cust.id, phone=norm_phone, normalized_phone=norm_phone, is_primary=True))
        db.commit()

    call_create = CallCreate(
        customer_id=test_cust.id,
        recipient_phone=norm_phone,
        caller_phone=payload.caller_phone,
        mode=payload.mode or "LIVE",
    )

    call = await LiveCallService.create_call(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        payload=call_create,
    )

    return SingleResponse(
        data={
            "call_id": call.id,
            "recipient_phone": PhoneNumberService.mask_phone(call.recipient_phone),
            "telephony_status": call.telephony_status,
            "mode": call.mode,
            "asterisk_channel_id": call.asterisk_channel_id,
            "created_at": call.created_at,
        }
    )


@router.get("/telephony/calls/{call_id}/diagnostics")
def get_call_diagnostics(
    call_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns safe diagnostic information for a specific physical or simulated call."""
    from app.db.models.call import Call
    from app.services.telephony_core.phone_number_service import PhoneNumberService

    call = db.execute(
        select(Call).where(Call.organization_id == current_user.organization_id, Call.id == call_id)
    ).scalar_one_or_none()

    if not call:
        raise NotFoundException("Call not found")

    return SingleResponse(
        data={
            "call_id": call.id,
            "mode": call.mode,
            "telephony_status": call.telephony_status,
            "ai_state": call.ai_state,
            "media_state": call.media_state,
            "asterisk_channel_id": call.asterisk_channel_id,
            "destination_masked": PhoneNumberService.mask_phone(call.recipient_phone),
            "caller_id": call.caller_phone,
            "direction": call.direction,
            "failure_code": call.failure_code,
            "failure_reason": call.failure_reason,
            "start_time": call.start_time,
            "answered_time": call.answered_time,
            "end_time": call.end_time,
            "duration_seconds": call.duration_seconds,
        }
    )
