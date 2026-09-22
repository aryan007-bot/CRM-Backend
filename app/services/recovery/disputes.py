import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException
from app.db.models.account import Account
from app.db.models.audit import AuditLog
from app.db.models.customer import Customer
from app.db.models.dispute import Dispute
from app.schemas.dispute import DisputeCreate, DisputeUpdate
from app.utils.pagination import paginate


class DisputeService:
    @classmethod
    def create_dispute(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        data: DisputeCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dispute:
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

        # Set account status to disputed while under investigation
        account.status = "disputed"

        dispute = Dispute(
            organization_id=organization_id,
            customer_id=data.customer_id,
            account_id=data.account_id,
            call_id=data.call_id,
            reason_category=data.reason_category,
            dispute_details=data.dispute_details,
            evidence_provided=data.evidence_provided,
            status="logged",
        )
        db.add(dispute)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_DISPUTE",
            entity_type="DISPUTE",
            entity_id=dispute.id,
            metadata_json={"reason": dispute.reason_category},
        )
        db.add(audit)
        db.commit()
        db.refresh(dispute)
        return dispute

    @classmethod
    def update_dispute(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        dispute_id: uuid.UUID,
        data: DisputeUpdate,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dispute:
        stmt = select(Dispute).where(
            Dispute.id == dispute_id,
            Dispute.organization_id == organization_id,
        )
        dispute = db.scalar(stmt)
        if not dispute:
            raise NotFoundException("Dispute not found", code="DISPUTE_NOT_FOUND")

        if data.status is not None:
            dispute.status = data.status
            if data.status in ("resolved", "rejected"):
                dispute.resolved_at = datetime.now(timezone.utc)
                account = db.get(Account, dispute.account_id)
                if account:
                    account.status = "active" if data.status == "rejected" else "paid"

        if data.assigned_to is not None:
            dispute.assigned_to = data.assigned_to
        if data.resolution_notes is not None:
            dispute.resolution_notes = data.resolution_notes

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="UPDATE_DISPUTE",
            entity_type="DISPUTE",
            entity_id=dispute.id,
            metadata_json={"status": dispute.status},
        )
        db.add(audit)
        db.commit()
        db.refresh(dispute)
        return dispute

    @classmethod
    def get_dispute(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        dispute_id: uuid.UUID,
    ) -> Dispute:
        stmt = select(Dispute).where(
            Dispute.id == dispute_id,
            Dispute.organization_id == organization_id,
        )
        dispute = db.scalar(stmt)
        if not dispute:
            raise NotFoundException("Dispute not found", code="DISPUTE_NOT_FOUND")
        return dispute

    @classmethod
    def assign_dispute(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        dispute_id: uuid.UUID,
        assigned_to: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dispute:
        dispute = cls.get_dispute(db, organization_id, dispute_id)
        dispute.assigned_to = assigned_to
        if dispute.status == "logged":
            dispute.status = "under_review"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="ASSIGN_DISPUTE",
            entity_type="DISPUTE",
            entity_id=dispute.id,
            metadata_json={"assigned_to": str(assigned_to)},
        )
        db.add(audit)
        db.commit()
        db.refresh(dispute)
        return dispute

    @classmethod
    def resolve_dispute(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        dispute_id: uuid.UUID,
        resolution_notes: str,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dispute:
        dispute = cls.get_dispute(db, organization_id, dispute_id)
        dispute.status = "resolved"
        dispute.resolution_notes = resolution_notes
        dispute.resolved_at = datetime.now(timezone.utc)

        # Restore or clear account dispute status
        account = db.get(Account, dispute.account_id)
        if account:
            account.status = "active"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="RESOLVE_DISPUTE",
            entity_type="DISPUTE",
            entity_id=dispute.id,
            metadata_json={"resolution_notes": resolution_notes},
        )
        db.add(audit)
        db.commit()
        db.refresh(dispute)
        return dispute

    @classmethod
    def escalate_dispute(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        dispute_id: uuid.UUID,
        notes: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> Dispute:
        dispute = cls.get_dispute(db, organization_id, dispute_id)
        dispute.status = "escalated"
        if notes:
            dispute.resolution_notes = (
                f"{dispute.resolution_notes}\nEscalation note: {notes}"
                if dispute.resolution_notes
                else f"Escalation note: {notes}"
            )

        from app.db.models.escalation import Escalation

        escalation = Escalation(
            organization_id=organization_id,
            customer_id=dispute.customer_id,
            account_id=dispute.account_id,
            call_id=dispute.call_id,
            reason="dispute_escalation",
            priority="high",
            status="open",
            resolution_notes=notes,
        )
        db.add(escalation)

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="ESCALATE_DISPUTE",
            entity_type="DISPUTE",
            entity_id=dispute.id,
            metadata_json={"notes": notes},
        )
        db.add(audit)
        db.commit()
        db.refresh(dispute)
        return dispute

    @classmethod
    def list_disputes(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        customer_id: Optional[uuid.UUID] = None,
        account_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        reason_category: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Dispute], int]:
        stmt = select(Dispute).where(Dispute.organization_id == organization_id)
        if customer_id:
            stmt = stmt.where(Dispute.customer_id == customer_id)
        if account_id:
            stmt = stmt.where(Dispute.account_id == account_id)
        if status:
            stmt = stmt.where(Dispute.status == status)
        if reason_category:
            stmt = stmt.where(Dispute.reason_category == reason_category)

        stmt = stmt.order_by(Dispute.created_at.desc())
        return paginate(db, stmt, page=page, page_size=page_size)
