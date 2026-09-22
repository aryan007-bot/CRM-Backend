import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictException, NotFoundException
from app.db.models.account import Account, AccountPayment
from app.db.models.audit import AuditLog
from app.db.models.creditor import Creditor
from app.db.models.customer import Customer
from app.schemas.account import AccountCreate, AccountPaymentCreate, AccountUpdate
from app.utils.pagination import paginate


class AccountService:
    @staticmethod
    def list_accounts(
        db: Session,
        organization_id: uuid.UUID,
        search: Optional[str] = None,
        status: Optional[str] = None,
        creditor_id: Optional[uuid.UUID] = None,
        customer_id: Optional[uuid.UUID] = None,
        due_date_from: Optional[date] = None,
        due_date_to: Optional[date] = None,
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "created_at",
        sort_direction: str = "desc",
    ) -> Tuple[List[Account], int]:
        query = select(Account).where(Account.organization_id == organization_id)

        if status:
            query = query.where(Account.status == status)

        if creditor_id:
            query = query.where(Account.creditor_id == creditor_id)

        if customer_id:
            query = query.where(Account.customer_id == customer_id)

        if due_date_from:
            query = query.where(Account.due_date >= due_date_from)

        if due_date_to:
            query = query.where(Account.due_date <= due_date_to)

        if search:
            s = f"%{search.strip()}%"
            query = query.outerjoin(Account.customer).where(
                or_(
                    Account.account_number.ilike(s),
                    Customer.name.ilike(s),
                )
            )

        sort_column = getattr(Account, sort_by, Account.created_at)
        if sort_direction.lower() == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        return paginate(db, query, page=page, page_size=page_size)

    @staticmethod
    def get_account(db: Session, organization_id: uuid.UUID, account_id: uuid.UUID) -> Account:
        stmt = select(Account).where(
            Account.id == account_id,
            Account.organization_id == organization_id,
        )
        account = db.scalar(stmt)
        if not account:
            raise NotFoundException("Account not found", code="ACCOUNT_NOT_FOUND")
        return account

    @staticmethod
    def create_account(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        data: AccountCreate,
    ) -> Account:
        # Verify customer belongs to organization
        customer = db.scalar(
            select(Customer).where(
                Customer.id == data.customer_id,
                Customer.organization_id == organization_id,
            )
        )
        if not customer:
            raise NotFoundException("Customer not found in this organization")

        # Verify creditor if provided
        if data.creditor_id:
            creditor = db.scalar(
                select(Creditor).where(
                    Creditor.id == data.creditor_id,
                    Creditor.organization_id == organization_id,
                )
            )
            if not creditor:
                raise NotFoundException("Creditor not found in this organization")

        # Verify account number uniqueness within organization
        existing = db.scalar(
            select(Account).where(
                Account.organization_id == organization_id,
                Account.account_number == data.account_number.strip(),
            )
        )
        if existing:
            raise ConflictException(
                f"Account '{data.account_number.strip()}' already exists in this organization",
                code="ACCOUNT_EXISTS",
            )

        account = Account(
            organization_id=organization_id,
            customer_id=data.customer_id,
            creditor_id=data.creditor_id,
            account_number=data.account_number.strip(),
            outstanding_amount=data.outstanding_amount,
            currency=data.currency,
            due_date=data.due_date,
            status=data.status,
        )
        db.add(account)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_ACCOUNT",
            entity_type="ACCOUNT",
            entity_id=account.id,
        )
        db.add(audit)
        db.commit()
        db.refresh(account)
        return account

    @staticmethod
    def update_account(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        account_id: uuid.UUID,
        data: AccountUpdate,
    ) -> Account:
        account = AccountService.get_account(db, organization_id, account_id)

        if data.outstanding_amount is not None:
            account.outstanding_amount = data.outstanding_amount
        if data.due_date is not None:
            account.due_date = data.due_date
        if data.status is not None:
            account.status = data.status
        if data.creditor_id is not None:
            creditor = db.scalar(
                select(Creditor).where(
                    Creditor.id == data.creditor_id,
                    Creditor.organization_id == organization_id,
                )
            )
            if not creditor:
                raise NotFoundException("Creditor not found in this organization")
            account.creditor_id = data.creditor_id

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="UPDATE_ACCOUNT",
            entity_type="ACCOUNT",
            entity_id=account.id,
        )
        db.add(audit)
        db.commit()
        db.refresh(account)
        return account

    @staticmethod
    def add_payment(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        account_id: uuid.UUID,
        data: AccountPaymentCreate,
    ) -> AccountPayment:
        account = AccountService.get_account(db, organization_id, account_id)

        payment = AccountPayment(
            account_id=account.id,
            amount=data.amount,
            currency=data.currency,
            payment_date=data.payment_date or datetime.now(),
            reference=data.reference,
            status=data.status,
            notes=data.notes,
        )
        db.add(payment)
        db.flush()

        # Update account outstanding amount if completed
        if data.status == "completed":
            account.outstanding_amount = max(Decimal("0.00"), account.outstanding_amount - data.amount)
            if account.outstanding_amount == Decimal("0.00"):
                account.status = "paid"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="RECORD_PAYMENT",
            entity_type="PAYMENT",
            entity_id=payment.id,
        )
        db.add(audit)
        db.commit()
        db.refresh(payment)
        return payment
