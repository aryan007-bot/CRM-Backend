import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException, ValidationException
from app.db.models.account import Account, AccountPayment
from app.db.models.audit import AuditLog
from app.db.models.customer import Customer
from app.db.models.payment_intent import PaymentIntent
from app.schemas.payment_intent import PaymentIntentCreate, PaymentIntentSendLink
from app.utils.pagination import paginate


class PaymentIntentService:
    @classmethod
    def create_intent(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        data: PaymentIntentCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> PaymentIntent:
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

        ref_id = f"pay_{uuid.uuid4().hex[:12]}"
        link_url = f"https://pay.agency.io/checkout/{ref_id}"
        expires_at = datetime.now(timezone.utc) + timedelta(hours=data.expires_in_hours)

        intent = PaymentIntent(
            organization_id=organization_id,
            customer_id=data.customer_id,
            account_id=data.account_id,
            call_id=data.call_id,
            amount=data.amount,
            payment_method=data.payment_method,
            status="initiated",
            reference_id=ref_id,
            link_url=link_url,
            expires_at=expires_at,
        )
        db.add(intent)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_PAYMENT_INTENT",
            entity_type="PAYMENT_INTENT",
            entity_id=intent.id,
            metadata_json={"amount": str(intent.amount), "ref": ref_id},
        )
        db.add(audit)
        db.commit()
        db.refresh(intent)
        return intent

    @classmethod
    def send_link(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        intent_id: uuid.UUID,
        data: PaymentIntentSendLink,
        user_id: Optional[uuid.UUID] = None,
    ) -> PaymentIntent:
        stmt = select(PaymentIntent).where(
            PaymentIntent.id == intent_id,
            PaymentIntent.organization_id == organization_id,
        )
        intent = db.scalar(stmt)
        if not intent:
            raise NotFoundException("Payment intent not found", code="PAYMENT_INTENT_NOT_FOUND")

        intent.status = "link_sent"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="SEND_PAYMENT_LINK",
            entity_type="PAYMENT_INTENT",
            entity_id=intent.id,
            metadata_json={"channel": data.channel, "recipient": data.recipient},
        )
        db.add(audit)
        db.commit()
        db.refresh(intent)
        return intent

    @classmethod
    def confirm_payment(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        intent_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> PaymentIntent:
        stmt = select(PaymentIntent).where(
            PaymentIntent.id == intent_id,
            PaymentIntent.organization_id == organization_id,
        )
        intent = db.scalar(stmt)
        if not intent:
            raise NotFoundException("Payment intent not found", code="PAYMENT_INTENT_NOT_FOUND")

        if intent.status == "confirmed":
            return intent

        account = db.get(Account, intent.account_id)
        if account:
            # Deduct from account outstanding
            new_amount = max(Decimal("0.00"), account.outstanding_amount - intent.amount)
            account.outstanding_amount = new_amount
            if new_amount == Decimal("0.00"):
                account.status = "paid"

            # Create AccountPayment
            payment = AccountPayment(
                account_id=account.id,
                amount=intent.amount,
                payment_date=datetime.now(timezone.utc),
                reference=intent.reference_id,
                notes="Confirmed via payment intent",
            )
            db.add(payment)

        intent.status = "confirmed"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CONFIRM_PAYMENT_INTENT",
            entity_type="PAYMENT_INTENT",
            entity_id=intent.id,
            metadata_json={"amount": str(intent.amount)},
        )
        db.add(audit)
        db.commit()
        db.refresh(intent)
        return intent

    @classmethod
    def get_intent(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        intent_id: uuid.UUID,
    ) -> PaymentIntent:
        stmt = select(PaymentIntent).where(
            PaymentIntent.id == intent_id,
            PaymentIntent.organization_id == organization_id,
        )
        intent = db.scalar(stmt)
        if not intent:
            raise NotFoundException("Payment intent not found", code="PAYMENT_INTENT_NOT_FOUND")
        return intent

    @classmethod
    def list_intents(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        customer_id: Optional[uuid.UUID] = None,
        account_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[PaymentIntent], int]:
        stmt = select(PaymentIntent).where(PaymentIntent.organization_id == organization_id)
        if customer_id:
            stmt = stmt.where(PaymentIntent.customer_id == customer_id)
        if account_id:
            stmt = stmt.where(PaymentIntent.account_id == account_id)
        if status:
            stmt = stmt.where(PaymentIntent.status == status)

        stmt = stmt.order_by(PaymentIntent.created_at.desc())
        return paginate(db, stmt, page=page, page_size=page_size)
