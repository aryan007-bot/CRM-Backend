import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.call import Call, TranscriptMessage
from app.db.models.campaign import Campaign
from app.db.models.customer import Customer
from app.db.models.organization import Organization
from app.db.models.user import User
from tests.conftest import auth_headers


def test_post_call_analysis_pipeline(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    headers = auth_headers(supervisor_a)

    customer = Customer(organization_id=test_org_a.id, name="Harold Finch")
    db.add(customer)
    db.flush()

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("25000.00"),
        status="active",
    )
    db.add(account)
    db.flush()

    campaign = Campaign(
        organization_id=test_org_a.id,
        name="Analysis Campaign",
        ai_disclosure_enabled=True,
        recording_disclosure_enabled=True,
    )
    db.add(campaign)
    db.flush()

    call = Call(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_id=account.id,
        campaign_id=campaign.id,
        caller_phone="+911122334455",
        recipient_phone="+919876543210",
        direction="OUTBOUND",
        status="ended",
        duration_seconds=95,
    )
    db.add(call)
    db.flush()

    # Transcripts with AI disclosure and customer promise to pay
    t1 = TranscriptMessage(
        call_id=call.id,
        organization_id=test_org_a.id,
        speaker="ai",
        text="Hello, this is an automated AI assistant calling from Alpha Bank regarding your account. This call is recorded for quality.",
    )
    t2 = TranscriptMessage(
        call_id=call.id,
        organization_id=test_org_a.id,
        speaker="customer",
        text="Yes I understand. I will pay tomorrow via UPI, please send the link.",
    )
    t3 = TranscriptMessage(
        call_id=call.id,
        organization_id=test_org_a.id,
        speaker="ai",
        text="Thank you. I have sent the payment link to your registered mobile number.",
    )
    db.add_all([t1, t2, t3])
    db.commit()

    # 1. Trigger Post-Call Analysis
    resp = client.post(f"/api/v1/calls/{call.id}/analyze", json={"force_reprocess": True}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["customer_intent"] == "willing_to_pay"
    assert data["sentiment"] == "positive"
    assert data["suggested_next_action"] == "send_payment_link"

    # Verify disclosures were found (0 violations)
    violations = data["compliance_violations"].get("violations", [])
    assert "MISSING_AI_DISCLOSURE" not in violations
    assert "MISSING_RECORDING_DISCLOSURE" not in violations

    # 2. Get Analysis
    get_resp = client.get(f"/api/v1/calls/{call.id}/analysis", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["call_id"] == str(call.id)
