import uuid
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.customer import Customer, CustomerPhone
from app.db.models.dnc import DncRecord
from app.db.models.organization import Organization
from app.services.recovery.eligibility import LeadEligibilityService


def _setup_lead(db: Session, org: Organization, outstanding: Decimal = Decimal("5000.00"), opted_out: bool = False):
    customer = Customer(
        organization_id=org.id,
        name="John Doe",
        is_opted_out=opted_out,
    )
    db.add(customer)
    db.flush()

    phone = CustomerPhone(
        customer_id=customer.id,
        phone="+919876543210",
        normalized_phone="+919876543210",
        is_primary=True,
    )
    db.add(phone)

    account = Account(
        organization_id=org.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=outstanding,
        status="active",
    )
    db.add(account)
    db.flush()

    campaign = Campaign(
        organization_id=org.id,
        name="Recovery Alpha",
        timezone="Asia/Kolkata",
        calling_start_time=time(0, 0),
        calling_end_time=time(23, 59),
        max_attempts=3,
        daily_attempt_limit=3,
        retry_cooldown_minutes=60,
        dnc_enforcement=True,
    )
    db.add(campaign)
    db.flush()

    lead = CampaignLead(
        campaign_id=campaign.id,
        account_id=account.id,
        status="pending",
        priority=1,
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    db.refresh(campaign)
    return campaign, lead, phone


def test_eligible_lead(db: Session, test_org_a: Organization):
    campaign, lead, phone = _setup_lead(db, test_org_a)
    is_eligible, reason, phone_num = LeadEligibilityService.evaluate_lead(db, campaign, lead)
    assert is_eligible is True
    assert reason is None
    assert phone_num == phone.normalized_phone


def test_ineligible_zero_balance(db: Session, test_org_a: Organization):
    campaign, lead, _ = _setup_lead(db, test_org_a, outstanding=Decimal("0.00"))
    is_eligible, reason, _ = LeadEligibilityService.evaluate_lead(db, campaign, lead)
    assert is_eligible is False
    assert reason == "NO_OUTSTANDING_BALANCE"


def test_ineligible_customer_opted_out(db: Session, test_org_a: Organization):
    campaign, lead, _ = _setup_lead(db, test_org_a, opted_out=True)
    is_eligible, reason, _ = LeadEligibilityService.evaluate_lead(db, campaign, lead)
    assert is_eligible is False
    assert reason == "CUSTOMER_OPTED_OUT"


def test_ineligible_max_attempts_reached(db: Session, test_org_a: Organization):
    campaign, lead, _ = _setup_lead(db, test_org_a)
    lead.attempt_count = 3
    db.commit()
    is_eligible, reason, _ = LeadEligibilityService.evaluate_lead(db, campaign, lead)
    assert is_eligible is False
    assert reason == "MAX_ATTEMPTS_EXCEEDED"


def test_ineligible_cooldown_active(db: Session, test_org_a: Organization):
    campaign, lead, _ = _setup_lead(db, test_org_a)
    now = datetime.now(timezone.utc)
    lead.last_attempt_at = now - timedelta(minutes=20)  # cooldown is 60 min
    db.commit()
    is_eligible, reason, _ = LeadEligibilityService.evaluate_lead(db, campaign, lead, at_time=now)
    assert is_eligible is False
    assert reason == "RETRY_COOLDOWN_ACTIVE"


def test_ineligible_phone_in_dnc(db: Session, test_org_a: Organization):
    campaign, lead, phone = _setup_lead(db, test_org_a)
    dnc = DncRecord(
        organization_id=test_org_a.id,
        phone_number=phone.normalized_phone,
        reason="customer_request",
        is_active=True,
    )
    db.add(dnc)
    db.commit()

    is_eligible, reason, _ = LeadEligibilityService.evaluate_lead(db, campaign, lead)
    assert is_eligible is False
    assert reason == "PHONE_IN_DNC"
