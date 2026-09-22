import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.db.models.account import Account, AccountPayment
from app.db.models.customer import Customer
from app.db.models.organization import Organization
from app.db.models.promise_to_pay import PromiseToPay
from app.services.recovery.ptp import PTPService


def test_ptp_reconciliation_kept(db: Session, test_org_a: Organization):
    customer = Customer(organization_id=test_org_a.id, name="Alice Doe")
    db.add(customer)
    db.flush()

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("10000.00"),
        status="active",
    )
    db.add(account)
    db.flush()

    ptp = PromiseToPay(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_id=account.id,
        amount=Decimal("5000.00"),
        promised_date=datetime.now(timezone.utc) + timedelta(days=2),
        grace_period_days=2,
        status="active",
    )
    db.add(ptp)
    db.commit()

    # Add matching payment
    payment = AccountPayment(
        account_id=account.id,
        amount=Decimal("5000.00"),
        payment_date=datetime.now(timezone.utc),
        reference="UPI-12345",
    )
    db.add(payment)
    db.commit()

    res = PTPService.reconcile_payments(db, test_org_a.id, ptp.id)
    assert res.current_status == "kept"
    assert res.total_paid == Decimal("5000.00")
    assert res.payments_matched == 1


def test_ptp_reconciliation_broken_after_grace_period(db: Session, test_org_a: Organization):
    customer = Customer(organization_id=test_org_a.id, name="Bob Doe")
    db.add(customer)
    db.flush()

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("10000.00"),
        status="active",
    )
    db.add(account)
    db.flush()

    # PTP promised 5 days ago with 2 days grace period -> expired!
    ptp = PromiseToPay(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_id=account.id,
        amount=Decimal("5000.00"),
        promised_date=datetime.now(timezone.utc) - timedelta(days=5),
        grace_period_days=2,
        status="active",
    )
    db.add(ptp)
    db.commit()

    res = PTPService.reconcile_payments(db, test_org_a.id, ptp.id)
    assert res.current_status == "broken"
    assert res.total_paid == Decimal("0.00")
