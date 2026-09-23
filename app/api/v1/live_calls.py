from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.db.models.call import Call
from app.db.models.user import User
from app.schemas.call import (
    CallCreate,
    CallDetailOut,
    CallDispositionUpdate,
    CallOut,
    CallTransferRequest,
    TranscriptMessageCreate,
    TranscriptMessageOut,
)
from app.schemas.common import PaginatedResponse, SingleResponse
from app.services.live_calls import LiveCallService

router = APIRouter(prefix="/live-calls", tags=["Live Calls"])


def _to_call_out(call: Call) -> dict:
    return {
        "id": call.id,
        "organization_id": call.organization_id,
        "customer_id": call.customer_id,
        "account_id": call.account_id,
        "campaign_id": call.campaign_id,
        "agent_id": call.agent_id,
        "gateway_id": call.gateway_id,
        "assigned_user_id": call.assigned_user_id,
        "caller_phone": call.caller_phone,
        "recipient_phone": call.recipient_phone,
        "direction": call.direction,
        "status": call.status,
        "mode": getattr(call, "mode", "LIVE"),
        "telephony_status": getattr(call, "telephony_status", "NOT_STARTED"),
        "ai_state": getattr(call, "ai_state", "IDLE"),
        "media_state": getattr(call, "media_state", "NO_MEDIA"),
        "asterisk_channel_id": getattr(call, "asterisk_channel_id", None),
        "failure_code": getattr(call, "failure_code", None),
        "failure_reason": getattr(call, "failure_reason", None),
        "disposition": call.disposition,
        "duration_seconds": call.duration_seconds,
        "customer_name": call.customer.name if call.customer else None,
        "agent_name": call.agent.name if call.agent else None,
        "account_number": call.account.account_number if call.account else None,
        "outstanding_amount": str(call.account.outstanding_amount) if call.account else None,
        "start_time": call.start_time,
        "answered_time": call.answered_time,
        "end_time": call.end_time,
        "created_at": call.created_at,
    }


@router.get("", response_model=PaginatedResponse[CallOut])
def list_calls(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = LiveCallService.list_calls(
        db=db,
        organization_id=current_user.organization_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    call_outs = [_to_call_out(c) for c in items]
    return PaginatedResponse(items=call_outs, page=page, page_size=page_size, total=total)


@router.post("", response_model=SingleResponse[CallOut], status_code=status.HTTP_201_CREATED)
async def create_call(
    payload: CallCreate,
    current_user: User = Depends(require_role("AGENT", "SUPERVISOR", "ORG_ADMIN")),
    db: Session = Depends(get_db),
):
    call = await LiveCallService.create_call(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        payload=payload,
    )
    return SingleResponse(data=_to_call_out(call))


@router.get("/{call_id}", response_model=SingleResponse[CallDetailOut])
def get_call(
    call_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    call = LiveCallService.get_call(db=db, organization_id=current_user.organization_id, call_id=call_id)
    data = _to_call_out(call)
    data["events"] = [
        {
            "id": e.id,
            "call_id": e.call_id,
            "sequence": e.sequence,
            "event_type": e.event_type,
            "payload": e.payload,
            "timestamp": e.timestamp,
        }
        for e in call.events
    ]
    data["transcripts"] = [
        {
            "id": t.id,
            "call_id": t.call_id,
            "speaker": t.speaker,
            "text": t.text,
            "is_final": t.is_final,
            "confidence": t.confidence,
            "start_time_offset": t.start_time_offset,
            "end_time_offset": t.end_time_offset,
            "timestamp": t.timestamp,
        }
        for t in call.transcripts
    ]
    return SingleResponse(data=data)


@router.post("/{call_id}/mute", response_model=SingleResponse[CallOut])
async def mute_call(
    call_id: uuid.UUID,
    current_user: User = Depends(require_role("AGENT", "SUPERVISOR", "ORG_ADMIN")),
    db: Session = Depends(get_db),
):
    call = await LiveCallService.mute_call(db, current_user.organization_id, call_id)
    return SingleResponse(data=_to_call_out(call))


@router.post("/{call_id}/unmute", response_model=SingleResponse[CallOut])
async def unmute_call(
    call_id: uuid.UUID,
    current_user: User = Depends(require_role("AGENT", "SUPERVISOR", "ORG_ADMIN")),
    db: Session = Depends(get_db),
):
    call = await LiveCallService.unmute_call(db, current_user.organization_id, call_id)
    return SingleResponse(data=_to_call_out(call))


@router.post("/{call_id}/hold", response_model=SingleResponse[CallOut])
async def hold_call(
    call_id: uuid.UUID,
    current_user: User = Depends(require_role("AGENT", "SUPERVISOR", "ORG_ADMIN")),
    db: Session = Depends(get_db),
):
    call = await LiveCallService.hold_call(db, current_user.organization_id, call_id)
    return SingleResponse(data=_to_call_out(call))


@router.post("/{call_id}/resume", response_model=SingleResponse[CallOut])
async def resume_call(
    call_id: uuid.UUID,
    current_user: User = Depends(require_role("AGENT", "SUPERVISOR", "ORG_ADMIN")),
    db: Session = Depends(get_db),
):
    call = await LiveCallService.resume_call(db, current_user.organization_id, call_id)
    return SingleResponse(data=_to_call_out(call))


@router.post("/{call_id}/transfer", response_model=SingleResponse[CallOut])
async def transfer_call(
    call_id: uuid.UUID,
    payload: CallTransferRequest,
    current_user: User = Depends(require_role("AGENT", "SUPERVISOR", "ORG_ADMIN")),
    db: Session = Depends(get_db),
):
    call = await LiveCallService.transfer_call(db, current_user.organization_id, call_id, payload)
    return SingleResponse(data=_to_call_out(call))


@router.post("/{call_id}/end", response_model=SingleResponse[CallOut])
async def end_call(
    call_id: uuid.UUID,
    current_user: User = Depends(require_role("AGENT", "SUPERVISOR", "ORG_ADMIN")),
    db: Session = Depends(get_db),
):
    call = await LiveCallService.end_call(db, current_user.organization_id, call_id)
    return SingleResponse(data=_to_call_out(call))


@router.post("/{call_id}/disposition", response_model=SingleResponse[CallOut])
def set_disposition(
    call_id: uuid.UUID,
    payload: CallDispositionUpdate,
    current_user: User = Depends(require_role("AGENT", "SUPERVISOR", "ORG_ADMIN")),
    db: Session = Depends(get_db),
):
    call = LiveCallService.set_disposition(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        call_id=call_id,
        payload=payload,
    )
    return SingleResponse(data=_to_call_out(call))


@router.post("/{call_id}/transcript", response_model=SingleResponse[TranscriptMessageOut], status_code=status.HTTP_201_CREATED)
async def append_transcript(
    call_id: uuid.UUID,
    payload: TranscriptMessageCreate,
    current_user: User = Depends(require_role("AGENT", "SUPERVISOR", "ORG_ADMIN")),
    db: Session = Depends(get_db),
):
    msg = await LiveCallService.append_transcript(db, current_user.organization_id, call_id, payload)
    return SingleResponse(
        data={
            "id": msg.id,
            "call_id": msg.call_id,
            "speaker": msg.speaker,
            "text": msg.text,
            "is_final": msg.is_final,
            "confidence": msg.confidence,
            "start_time_offset": msg.start_time_offset,
            "end_time_offset": msg.end_time_offset,
            "timestamp": msg.timestamp,
        }
    )
