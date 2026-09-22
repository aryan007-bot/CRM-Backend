import uuid
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConflictException, NotFoundException
from app.db.models.audit import AuditLog
from app.db.models.dnc import DncRecord
from app.schemas.recovery import DncRecordCreate
from app.utils.pagination import paginate


class DncService:
    @classmethod
    def add_dnc(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        data: DncRecordCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> DncRecord:
        normalized = data.phone_number.strip()
        existing = db.scalar(
            select(DncRecord).where(
                DncRecord.organization_id == organization_id,
                DncRecord.phone_number == normalized,
            )
        )
        if existing:
            if existing.is_active:
                raise ConflictException("Phone number already in DNC registry", code="PHONE_ALREADY_IN_DNC")
            existing.is_active = True
            existing.reason = data.reason
            existing.notes = data.notes
            existing.added_by = user_id
            db.commit()
            db.refresh(existing)
            return existing

        record = DncRecord(
            organization_id=organization_id,
            phone_number=normalized,
            customer_id=data.customer_id,
            reason=data.reason,
            is_active=True,
            added_by=user_id,
            notes=data.notes,
        )
        db.add(record)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="ADD_DNC_RECORD",
            entity_type="DNC_RECORD",
            entity_id=record.id,
            metadata_json={"phone": record.phone_number, "reason": record.reason},
        )
        db.add(audit)
        db.commit()
        db.refresh(record)
        return record

    @classmethod
    def remove_dnc(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        phone_number: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> DncRecord:
        normalized = phone_number.strip()
        record = db.scalar(
            select(DncRecord).where(
                DncRecord.organization_id == organization_id,
                DncRecord.phone_number == normalized,
                DncRecord.is_active == True,
            )
        )
        if not record:
            raise NotFoundException("DNC record not found", code="DNC_RECORD_NOT_FOUND")

        record.is_active = False

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="REMOVE_DNC_RECORD",
            entity_type="DNC_RECORD",
            entity_id=record.id,
            metadata_json={"phone": record.phone_number},
        )
        db.add(audit)
        db.commit()
        db.refresh(record)
        return record

    @classmethod
    def list_dnc(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[DncRecord], int]:
        stmt = select(DncRecord).where(DncRecord.organization_id == organization_id)
        if is_active is not None:
            stmt = stmt.where(DncRecord.is_active == is_active)

        stmt = stmt.order_by(DncRecord.created_at.desc())
        return paginate(db, stmt, page=page, page_size=page_size)
