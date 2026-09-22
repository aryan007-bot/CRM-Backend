import uuid
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException
from app.db.models.account import Account
from app.db.models.audit import AuditLog
from app.db.models.callback import Callback
from app.db.models.customer import Customer
from app.schemas.callback import CallbackCreate, CallbackUpdate
from app.utils.pagination import paginate


class CallbackService:
    @classmethod
    def create_callback(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        data: CallbackCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> Callback:
        customer = db.scalar(
            select(Customer).where(
                Customer.id == data.customer_id,
                Customer.organization_id == organization_id,
            )
        )
        if not customer:
            raise NotFoundException("Customer not found", code="CUSTOMER_NOT_FOUND")

        account = db.scalar(
            select(Account).where(
                Account.id == data.account_id,
                Account.organization_id == organization_id,
            )
        )
        if not account:
            raise NotFoundException("Account not found", code="ACCOUNT_NOT_FOUND")

        callback = Callback(
            organization_id=organization_id,
            customer_id=data.customer_id,
            account_id=data.account_id,
            call_id=data.call_id,
            scheduled_time=data.scheduled_time,
            phone_number=data.phone_number,
            status="pending",
            requested_by=data.requested_by,
            notes=data.notes,
        )
        db.add(callback)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_CALLBACK",
            entity_type="CALLBACK",
            entity_id=callback.id,
            metadata_json={"time": callback.scheduled_time.isoformat(), "phone": callback.phone_number},
        )
        db.add(audit)
        db.commit()
        db.refresh(callback)
        return callback

    @classmethod
    def update_callback(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        callback_id: uuid.UUID,
        data: CallbackUpdate,
        user_id: Optional[uuid.UUID] = None,
    ) -> Callback:
        stmt = select(Callback).where(
            Callback.id == callback_id,
            Callback.organization_id == organization_id,
        )
        callback = db.scalar(stmt)
        if not callback:
            raise NotFoundException("Callback not found", code="CALLBACK_NOT_FOUND")

        if data.scheduled_time is not None:
            callback.scheduled_time = data.scheduled_time
        if data.phone_number is not None:
            callback.phone_number = data.phone_number
        if data.status is not None:
            callback.status = data.status
        if data.notes is not None:
            callback.notes = data.notes

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="UPDATE_CALLBACK",
            entity_type="CALLBACK",
            entity_id=callback.id,
            metadata_json={"status": callback.status},
        )
        db.add(audit)
        db.commit()
        db.refresh(callback)
        return callback

    @classmethod
    def get_callback(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        callback_id: uuid.UUID,
    ) -> Callback:
        stmt = select(Callback).where(
            Callback.id == callback_id,
            Callback.organization_id == organization_id,
        )
        callback = db.scalar(stmt)
        if not callback:
            raise NotFoundException("Callback not found", code="CALLBACK_NOT_FOUND")
        return callback

    @classmethod
    def cancel_callback(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        callback_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Callback:
        callback = cls.get_callback(db, organization_id, callback_id)
        callback.status = "cancelled"
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CANCEL_CALLBACK",
            entity_type="CALLBACK",
            entity_id=callback.id,
            metadata_json={"status": "cancelled"},
        )
        db.add(audit)
        db.commit()
        db.refresh(callback)
        return callback

    @classmethod
    def complete_callback(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        callback_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Callback:
        callback = cls.get_callback(db, organization_id, callback_id)
        callback.status = "completed"
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="COMPLETE_CALLBACK",
            entity_type="CALLBACK",
            entity_id=callback.id,
            metadata_json={"status": "completed"},
        )
        db.add(audit)
        db.commit()
        db.refresh(callback)
        return callback

    @classmethod
    def list_callbacks(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        customer_id: Optional[uuid.UUID] = None,
        account_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Callback], int]:
        stmt = select(Callback).where(Callback.organization_id == organization_id)
        if customer_id:
            stmt = stmt.where(Callback.customer_id == customer_id)
        if account_id:
            stmt = stmt.where(Callback.account_id == account_id)
        if status:
            stmt = stmt.where(Callback.status == status)

        stmt = stmt.order_by(Callback.scheduled_time.asc())
        return paginate(db, stmt, page=page, page_size=page_size)
