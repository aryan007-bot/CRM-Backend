import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException
from app.db.models.account import Account, AccountPayment
from app.db.models.audit import AuditLog
from app.db.models.customer import Customer
from app.db.models.promise_to_pay import PromiseToPay
from app.schemas.ptp import PTPCreate, PTPReconciliationResponse, PTPUpdate
from app.utils.pagination import paginate


class PTPService:
    @classmethod
    def create_ptp(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        data: PTPCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> PromiseToPay:
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

        ptp = PromiseToPay(
            organization_id=organization_id,
            customer_id=data.customer_id,
            account_id=data.account_id,
            call_id=data.call_id,
            outcome_id=data.outcome_id,
            amount=data.amount,
            promised_date=data.promised_date,
            grace_period_days=data.grace_period_days,
            status="active",
            notes=data.notes,
        )
        db.add(ptp)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_PTP",
            entity_type="PROMISE_TO_PAY",
            entity_id=ptp.id,
            metadata_json={"amount": str(ptp.amount), "date": ptp.promised_date.isoformat()},
        )
        db.add(audit)
        db.commit()
        db.refresh(ptp)
        return ptp

    @classmethod
    def update_ptp(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        ptp_id: uuid.UUID,
        data: PTPUpdate,
        user_id: Optional[uuid.UUID] = None,
    ) -> PromiseToPay:
        stmt = select(PromiseToPay).where(
            PromiseToPay.id == ptp_id,
            PromiseToPay.organization_id == organization_id,
        )
        ptp = db.scalar(stmt)
        if not ptp:
            raise NotFoundException("PTP not found", code="PTP_NOT_FOUND")

        if data.status is not None:
            ptp.status = data.status
        if data.notes is not None:
            ptp.notes = data.notes
        if data.promised_date is not None:
            ptp.promised_date = data.promised_date
        if data.grace_period_days is not None:
            ptp.grace_period_days = data.grace_period_days

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="UPDATE_PTP",
            entity_type="PROMISE_TO_PAY",
            entity_id=ptp.id,
            metadata_json={"status": ptp.status},
        )
        db.add(audit)
        db.commit()
        db.refresh(ptp)
        return ptp

    @classmethod
    def reconcile_payments(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        ptp_id: uuid.UUID,
    ) -> PTPReconciliationResponse:
        stmt = select(PromiseToPay).where(
            PromiseToPay.id == ptp_id,
            PromiseToPay.organization_id == organization_id,
        )
        ptp = db.scalar(stmt)
        if not ptp:
            raise NotFoundException("PTP not found", code="PTP_NOT_FOUND")

        previous_status = ptp.status
        now = datetime.now(timezone.utc)

        # Query all payments for this account recorded on or after ptp creation
        created_date = ptp.created_at.date() if ptp.created_at else now.date()
        payments = db.scalars(
            select(AccountPayment).where(
                AccountPayment.account_id == ptp.account_id,
                AccountPayment.payment_date >= created_date,
            )
        ).all()

        total_paid = sum((p.amount for p in payments), Decimal("0.00"))

        if total_paid >= ptp.amount:
            ptp.status = "kept"
        else:
            # Check if grace period has passed
            promised_dt = ptp.promised_date
            if promised_dt.tzinfo is None:
                promised_dt = promised_dt.replace(tzinfo=timezone.utc)

            deadline = promised_dt + timedelta(days=ptp.grace_period_days)
            if now > deadline and ptp.status == "active":
                ptp.status = "broken"

        db.commit()
        db.refresh(ptp)

        return PTPReconciliationResponse(
            ptp_id=ptp.id,
            previous_status=previous_status,
            current_status=ptp.status,
            payments_matched=len(payments),
            total_paid=total_paid,
            reconciled_at=now,
        )

    @classmethod
    def reconcile_all_active(
        cls,
        db: Session,
        organization_id: uuid.UUID,
    ) -> List[PTPReconciliationResponse]:
        active_ptps = db.scalars(
            select(PromiseToPay).where(
                PromiseToPay.organization_id == organization_id,
                PromiseToPay.status == "active",
            )
        ).all()

        return [cls.reconcile_payments(db, organization_id, ptp.id) for ptp in active_ptps]

    @classmethod
    def list_ptps(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        customer_id: Optional[uuid.UUID] = None,
        account_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[PromiseToPay], int]:
        stmt = select(PromiseToPay).where(PromiseToPay.organization_id == organization_id)
        if customer_id:
            stmt = stmt.where(PromiseToPay.customer_id == customer_id)
        if account_id:
            stmt = stmt.where(PromiseToPay.account_id == account_id)
        if status:
            stmt = stmt.where(PromiseToPay.status == status)

        stmt = stmt.order_by(PromiseToPay.promised_date.asc())
        return paginate(db, stmt, page=page, page_size=page_size)

    @classmethod
    def get_ptp(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        ptp_id: uuid.UUID,
    ) -> PromiseToPay:
        stmt = select(PromiseToPay).where(
            PromiseToPay.id == ptp_id,
            PromiseToPay.organization_id == organization_id,
        )
        ptp = db.scalar(stmt)
        if not ptp:
            raise NotFoundException("PTP not found", code="PTP_NOT_FOUND")
        return ptp

    @classmethod
    def confirm_ptp(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        ptp_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> PromiseToPay:
        ptp = cls.get_ptp(db, organization_id, ptp_id)
        ptp.status = "confirmed"
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CONFIRM_PTP",
            entity_type="PROMISE_TO_PAY",
            entity_id=ptp.id,
            metadata_json={"status": "confirmed"},
        )
        db.add(audit)
        db.commit()
        db.refresh(ptp)
        return ptp

    @classmethod
    def cancel_ptp(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        ptp_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> PromiseToPay:
        ptp = cls.get_ptp(db, organization_id, ptp_id)
        ptp.status = "cancelled"
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CANCEL_PTP",
            entity_type="PROMISE_TO_PAY",
            entity_id=ptp.id,
            metadata_json={"status": "cancelled"},
        )
        db.add(audit)
        db.commit()
        db.refresh(ptp)
        return ptp
