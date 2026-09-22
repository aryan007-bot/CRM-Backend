from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, joinedload

from app.adapters.telephony.asterisk import AsteriskTelephonyAdapter
from app.core.errors import ConflictException, NotFoundException, ValidationException
from app.db.models.account import Account
from app.db.models.ai_agent import AiAgent
from app.db.models.audit import AuditLog
from app.db.models.call import Call, CallEvent, TranscriptMessage
from app.db.models.customer import Customer
from app.schemas.call import CallCreate, CallDispositionUpdate, CallTransferRequest, TranscriptMessageCreate
from app.services.realtime.manager import realtime_manager
from app.utils.pagination import paginate

asterisk_adapter = AsteriskTelephonyAdapter()

VALID_STATE_TRANSITIONS = {
    "created": ["connecting", "ringing", "connected", "failed", "ended"],
    "connecting": ["ringing", "connected", "failed", "ended"],
    "ringing": ["connected", "failed", "ended"],
    "connected": ["ai_talking", "customer_talking", "on_hold", "transferring", "human_connected", "ending", "ended"],
    "ai_talking": ["customer_talking", "on_hold", "transferring", "human_connected", "ending", "ended", "connected"],
    "customer_talking": ["ai_talking", "on_hold", "transferring", "human_connected", "ending", "ended", "connected"],
    "on_hold": ["connected", "ai_talking", "customer_talking", "transferring", "human_connected", "ending", "ended"],
    "transferring": ["human_connected", "connected", "failed", "ended"],
    "human_connected": ["ending", "ended"],
    "ending": ["ended", "failed"],
    "ended": [],
    "failed": [],
}


class LiveCallService:
    @staticmethod
    def _validate_transition(current_status: str, target_status: str):
        allowed = VALID_STATE_TRANSITIONS.get(current_status, [])
        if target_status not in allowed:
            raise ValidationException(
                f"Invalid call state transition: cannot change status from '{current_status}' to '{target_status}'."
            )

    @classmethod
    async def create_call(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        payload: CallCreate,
    ) -> Call:
        # Verify customer belongs to tenant
        customer = db.execute(
            select(Customer).where(Customer.organization_id == organization_id, Customer.id == payload.customer_id)
        ).scalar_one_or_none()
        if not customer:
            raise NotFoundException("Customer not found")

        call = Call(
            organization_id=organization_id,
            customer_id=payload.customer_id,
            account_id=payload.account_id,
            campaign_id=payload.campaign_id,
            agent_id=payload.agent_id,
            caller_phone=payload.caller_phone or "+919876543210",
            recipient_phone=payload.recipient_phone,
            direction="OUTBOUND",
            status="created",
            start_time=datetime.now(timezone.utc),
            duration_seconds=0,
        )
        db.add(call)
        db.flush()

        # Originate via Telephony Adapter
        asterisk_adapter.originate_call(call.caller_phone, call.recipient_phone, channel_id=str(call.id))

        # Initial call event
        event = CallEvent(
            call_id=call.id,
            organization_id=organization_id,
            sequence=1,
            event_type="call.created",
            payload={"caller": call.caller_phone, "recipient": call.recipient_phone},
        )
        db.add(event)

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_CALL",
            entity_type="call",
            entity_id=call.id,
            metadata_json={"recipient": call.recipient_phone},
        )
        db.add(audit)
        db.commit()
        db.refresh(call)

        await realtime_manager.broadcast_event(
            organization_id=organization_id,
            call_id=call.id,
            event_type="call.created",
            data={"status": call.status, "recipient": call.recipient_phone},
            sequence=1,
        )
        return call

    @classmethod
    async def transition_state(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        call_id: uuid.UUID,
        new_status: str,
        extra_payload: Optional[Dict[str, Any]] = None,
    ) -> Call:
        call = cls.get_call(db, organization_id, call_id)
        cls._validate_transition(call.status, new_status)

        old_status = call.status
        call.status = new_status
        now = datetime.now(timezone.utc)

        if new_status == "connected" and not call.answered_time:
            call.answered_time = now
        elif new_status in ("ended", "failed"):
            call.end_time = now
            if call.answered_time:
                ans_time = call.answered_time
                if ans_time.tzinfo is None:
                    ans_time = ans_time.replace(tzinfo=timezone.utc)
                call.duration_seconds = int((now - ans_time).total_seconds())

        seq = await realtime_manager.get_next_sequence(call_id)
        event_payload = {"from_status": old_status, "to_status": new_status}
        if extra_payload:
            event_payload.update(extra_payload)

        event = CallEvent(
            call_id=call.id,
            organization_id=organization_id,
            sequence=seq,
            event_type=f"call.{new_status}",
            payload=event_payload,
        )
        db.add(event)
        db.commit()
        db.refresh(call)

        await realtime_manager.broadcast_event(
            organization_id=organization_id,
            call_id=call.id,
            event_type=f"call.{new_status}",
            data=event_payload,
            sequence=seq,
        )
        return call

    @staticmethod
    def get_call(db: Session, organization_id: uuid.UUID, call_id: uuid.UUID) -> Call:
        query = (
            select(Call)
            .where(Call.organization_id == organization_id, Call.id == call_id)
            .options(
                joinedload(Call.customer),
                joinedload(Call.account),
                joinedload(Call.agent),
                joinedload(Call.events),
                joinedload(Call.transcripts),
            )
        )
        call = db.execute(query).unique().scalar_one_or_none()
        if not call:
            raise NotFoundException("Call not found")
        return call

    @staticmethod
    def list_calls(
        db: Session,
        organization_id: uuid.UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Call], int]:
        query = (
            select(Call)
            .where(Call.organization_id == organization_id)
            .options(
                joinedload(Call.customer),
                joinedload(Call.account),
                joinedload(Call.agent),
            )
            .order_by(desc(Call.created_at))
        )
        if status:
            query = query.where(Call.status == status)
        return paginate(db, query, page, page_size)

    @classmethod
    async def mute_call(cls, db: Session, organization_id: uuid.UUID, call_id: uuid.UUID) -> Call:
        call = cls.get_call(db, organization_id, call_id)
        if call.status in ("ended", "failed"):
            raise ValidationException("Cannot mute an ended call.")
        asterisk_adapter.mute_channel(str(call_id))
        seq = await realtime_manager.get_next_sequence(call_id)
        await realtime_manager.broadcast_event(
            organization_id=organization_id,
            call_id=call_id,
            event_type="call.muted",
            data={"muted": True},
            sequence=seq,
        )
        return call

    @classmethod
    async def unmute_call(cls, db: Session, organization_id: uuid.UUID, call_id: uuid.UUID) -> Call:
        call = cls.get_call(db, organization_id, call_id)
        if call.status in ("ended", "failed"):
            raise ValidationException("Cannot unmute an ended call.")
        asterisk_adapter.unmute_channel(str(call_id))
        seq = await realtime_manager.get_next_sequence(call_id)
        await realtime_manager.broadcast_event(
            organization_id=organization_id,
            call_id=call_id,
            event_type="call.muted",
            data={"muted": False},
            sequence=seq,
        )
        return call

    @classmethod
    async def hold_call(cls, db: Session, organization_id: uuid.UUID, call_id: uuid.UUID) -> Call:
        return await cls.transition_state(db, organization_id, call_id, "on_hold")

    @classmethod
    async def resume_call(cls, db: Session, organization_id: uuid.UUID, call_id: uuid.UUID) -> Call:
        return await cls.transition_state(db, organization_id, call_id, "connected")

    @classmethod
    async def transfer_call(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        call_id: uuid.UUID,
        payload: CallTransferRequest,
    ) -> Call:
        call = cls.get_call(db, organization_id, call_id)
        if call.status in ("ended", "failed"):
            raise ValidationException("Cannot transfer an ended call.")
        if call.status == "human_connected":
            raise ConflictException("Call is already transferred to a human agent.")

        target = payload.target_extension or "agent-queue"
        asterisk_adapter.transfer_channel(str(call_id), target)

        if payload.target_user_id:
            call.assigned_user_id = payload.target_user_id

        return await cls.transition_state(
            db, organization_id, call_id, "human_connected", extra_payload={"transferred_to": target}
        )

    @classmethod
    async def end_call(cls, db: Session, organization_id: uuid.UUID, call_id: uuid.UUID) -> Call:
        call = cls.get_call(db, organization_id, call_id)
        if call.status in ("ended", "failed"):
            return call
        asterisk_adapter.hangup_channel(str(call_id))
        return await cls.transition_state(db, organization_id, call_id, "ended")

    @classmethod
    def set_disposition(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        call_id: uuid.UUID,
        payload: CallDispositionUpdate,
    ) -> Call:
        call = cls.get_call(db, organization_id, call_id)
        call.disposition = payload.disposition.upper()
        if payload.notes:
            call.notes = payload.notes
        db.commit()
        db.refresh(call)
        return call

    @classmethod
    async def append_transcript(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        call_id: uuid.UUID,
        payload: TranscriptMessageCreate,
    ) -> TranscriptMessage:
        call = cls.get_call(db, organization_id, call_id)

        msg = TranscriptMessage(
            call_id=call.id,
            organization_id=organization_id,
            speaker=payload.speaker,
            text=payload.text.strip(),
            is_final=payload.is_final,
            confidence=payload.confidence or 0.95,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)

        seq = await realtime_manager.get_next_sequence(call_id)
        event_name = "transcript.final" if payload.is_final else "transcript.partial"
        await realtime_manager.broadcast_event(
            organization_id=organization_id,
            call_id=call_id,
            event_type=event_name,
            data={
                "id": str(msg.id),
                "speaker": msg.speaker,
                "text": msg.text,
                "is_final": msg.is_final,
                "timestamp": msg.timestamp.isoformat(),
            },
            sequence=seq,
        )
        return msg
