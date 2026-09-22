import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException
from app.db.models.account import Account
from app.db.models.audit import AuditLog
from app.db.models.customer import Customer
from app.db.models.escalation import Escalation
from app.schemas.escalation import EscalationCreate, EscalationUpdate
from app.utils.pagination import paginate


class EscalationService:
    @classmethod
    def create_escalation(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        data: EscalationCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> Escalation:
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

        escalation = Escalation(
            organization_id=organization_id,
            customer_id=data.customer_id,
            account_id=data.account_id,
            call_id=data.call_id,
            reason=data.reason,
            priority=data.priority,
            status="open",
            resolution_notes=data.resolution_notes,
        )
        db.add(escalation)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_ESCALATION",
            entity_type="ESCALATION",
            entity_id=escalation.id,
            metadata_json={"reason": escalation.reason, "priority": escalation.priority},
        )
        db.add(audit)
        db.commit()
        db.refresh(escalation)
        return escalation

    @classmethod
    def update_escalation(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        escalation_id: uuid.UUID,
        data: EscalationUpdate,
        user_id: Optional[uuid.UUID] = None,
    ) -> Escalation:
        stmt = select(Escalation).where(
            Escalation.id == escalation_id,
            Escalation.organization_id == organization_id,
        )
        escalation = db.scalar(stmt)
        if not escalation:
            raise NotFoundException("Escalation not found", code="ESCALATION_NOT_FOUND")

        if data.status is not None:
            escalation.status = data.status
            if data.status in ("resolved", "dismissed"):
                escalation.resolved_at = datetime.now(timezone.utc)

        if data.escalated_to is not None:
            escalation.escalated_to = data.escalated_to
        if data.priority is not None:
            escalation.priority = data.priority
        if data.resolution_notes is not None:
            escalation.resolution_notes = data.resolution_notes

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="UPDATE_ESCALATION",
            entity_type="ESCALATION",
            entity_id=escalation.id,
            metadata_json={"status": escalation.status},
        )
        db.add(audit)
        db.commit()
        db.refresh(escalation)
        return escalation

    @classmethod
    def get_escalation(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        escalation_id: uuid.UUID,
    ) -> Escalation:
        stmt = select(Escalation).where(
            Escalation.id == escalation_id,
            Escalation.organization_id == organization_id,
        )
        escalation = db.scalar(stmt)
        if not escalation:
            raise NotFoundException("Escalation not found", code="ESCALATION_NOT_FOUND")
        return escalation

    @classmethod
    def assign_escalation(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        escalation_id: uuid.UUID,
        escalated_to: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Escalation:
        escalation = cls.get_escalation(db, organization_id, escalation_id)
        escalation.escalated_to = escalated_to
        if escalation.status == "open":
            escalation.status = "investigating"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="ASSIGN_ESCALATION",
            entity_type="ESCALATION",
            entity_id=escalation.id,
            metadata_json={"escalated_to": str(escalated_to)},
        )
        db.add(audit)
        db.commit()
        db.refresh(escalation)
        return escalation

    @classmethod
    def resolve_escalation(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        escalation_id: uuid.UUID,
        resolution_notes: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> Escalation:
        escalation = cls.get_escalation(db, organization_id, escalation_id)
        escalation.status = "resolved"
        escalation.resolution_notes = resolution_notes
        escalation.resolved_at = datetime.now(timezone.utc)

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="RESOLVE_ESCALATION",
            entity_type="ESCALATION",
            entity_id=escalation.id,
            metadata_json={"resolution_notes": resolution_notes},
        )
        db.add(audit)
        db.commit()
        db.refresh(escalation)
        return escalation

    @classmethod
    def cancel_escalation(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        escalation_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Escalation:
        escalation = cls.get_escalation(db, organization_id, escalation_id)
        escalation.status = "dismissed"
        escalation.resolved_at = datetime.now(timezone.utc)

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CANCEL_ESCALATION",
            entity_type="ESCALATION",
            entity_id=escalation.id,
            metadata_json={"status": "dismissed"},
        )
        db.add(audit)
        db.commit()
        db.refresh(escalation)
        return escalation

    @classmethod
    def list_escalations(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        customer_id: Optional[uuid.UUID] = None,
        account_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Escalation], int]:
        stmt = select(Escalation).where(Escalation.organization_id == organization_id)
        if customer_id:
            stmt = stmt.where(Escalation.customer_id == customer_id)
        if account_id:
            stmt = stmt.where(Escalation.account_id == account_id)
        if status:
            stmt = stmt.where(Escalation.status == status)
        if priority:
            stmt = stmt.where(Escalation.priority == priority)

        stmt = stmt.order_by(Escalation.created_at.desc())
        return paginate(db, stmt, page=page, page_size=page_size)
