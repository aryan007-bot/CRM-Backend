import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.ai_agent import AiAgent, VoiceProfile
from app.db.models.call import Call, TranscriptMessage
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.creditor import Creditor
from app.db.models.customer import Customer, CustomerPhone
from app.db.models.organization import Organization
from app.db.models.user import User
from app.services.recovery.exports import ExportService
from tests.conftest import auth_headers


def test_master_e2e_recovery_lifecycle(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    """MASTER E2E RECOVERY TEST
    Covers the full Phase 3 recovery journey:
    Campaign -> Validation -> Start -> Queue Reservation -> Call -> Outcome -> Analysis -> Automation -> Payment -> Reconciliation -> Export
    """
    headers = auth_headers(supervisor_a)

    # 1. Setup Creditor, Agent, Voice Profile
    creditor = Creditor(
        organization_id=test_org_a.id,
        name="Apex Financial Corp",
    )
    db.add(creditor)

    agent = AiAgent(
        organization_id=test_org_a.id,
        name="Recovery Specialist Sarah",
        language="en-IN",
        model="gpt-4o-mini",
        system_prompt="You are a respectful debt collection assistant.",
        disclosure="This is an automated AI assistant calling from Apex Financial. This call is recorded.",
        status="ready",
        is_active=True,
    )
    db.add(agent)
    db.flush()

    voice = VoiceProfile(
        organization_id=test_org_a.id,
        agent_id=agent.id,
        name="Sarah Professional Voice",
        provider="chatterbox",
        audio_path="/mock/sarah.wav",
        sample_rate=24000,
        status="ready",
    )
    db.add(voice)

    # 2. Setup Customer & Account
    customer = Customer(
        organization_id=test_org_a.id,
        name="Rajesh Kumar",
    )
    db.add(customer)
    db.flush()

    phone = CustomerPhone(
        customer_id=customer.id,
        phone="+919876501234",
        normalized_phone="+919876501234",
        is_primary=True,
    )
    db.add(phone)

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        creditor_id=creditor.id,
        account_number=f"APEX-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("12500.00"),
        status="active",
    )
    db.add(account)
    db.commit()

    # 3. Setup Automation Rule for PTP
    rule_resp = client.post(
        "/api/v1/automation/rules",
        json={
            "name": "PTP Confirmation SMS",
            "event_trigger": "ptp_created",
            "action_type": "send_sms",
            "action_template": "Dear customer, your commitment for Apex Financial is registered.",
            "is_active": True,
            "delay_minutes": 0,
        },
        headers=headers,
    )
    assert rule_resp.status_code == 201

    # 4. Create Campaign
    camp_payload = {
        "name": "Apex Q3 Recovery Campaign",
        "campaign_type": "recovery",
        "priority": 1,
        "creditor_id": str(creditor.id),
        "ai_agent_id": str(agent.id),
        "voice_profile_id": str(voice.id),
        "language_mode": "en-IN",
        "timezone": "Asia/Kolkata",
        "calling_start_time": "00:00:00",
        "calling_end_time": "23:59:59",
        "max_attempts": 3,
        "daily_attempt_limit": 3,
        "retry_cooldown_minutes": 60,
        "concurrency_limit": 5,
        "dnc_enforcement": True,
        "ai_disclosure_enabled": True,
        "recording_disclosure_enabled": True,
        "human_escalation_enabled": True,
        "follow_up_enabled": True,
    }
    create_camp = client.post("/api/v1/campaigns", json=camp_payload, headers=headers)
    assert create_camp.status_code == 201
    campaign_id = create_camp.json()["data"]["id"]

    # 5. Add Debtor Lead to Campaign
    add_leads = client.post(
        f"/api/v1/campaigns/{campaign_id}/leads",
        json={"account_ids": [str(account.id)], "priority": 1},
        headers=headers,
    )
    assert add_leads.status_code == 201

    # 6. Validate Campaign
    val_resp = client.post(f"/api/v1/campaigns/{campaign_id}/validate", headers=headers)
    assert val_resp.status_code == 200
    assert val_resp.json()["data"]["valid"] is True
    assert val_resp.json()["data"]["eligible_leads"] == 1

    # 7. Start Campaign -> Enqueues into Dial Queue
    start_resp = client.post(f"/api/v1/campaigns/{campaign_id}/start", headers=headers)
    assert start_resp.status_code == 200
    assert start_resp.json()["data"]["status"] == "active"

    # 8. Reserve Lead from Dial Queue
    reserve_resp = client.post(
        "/api/v1/recovery/queue/reserve",
        json={"worker_id": "recovery-worker-alpha", "batch_size": 1, "campaign_id": campaign_id},
        headers=headers,
    )
    assert reserve_resp.status_code == 200
    reserved_items = reserve_resp.json()["data"]["items"]
    assert len(reserved_items) == 1
    queue_item_id = reserved_items[0]["id"]
    assert reserved_items[0]["phone_number"] == "+919876501234"

    # 9. Create Call record and Transcripts
    call = Call(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_id=account.id,
        campaign_id=uuid.UUID(campaign_id),
        agent_id=agent.id,
        caller_phone="+918012345678",
        recipient_phone="+919876501234",
        direction="OUTBOUND",
        status="ended",
        duration_seconds=120,
    )
    db.add(call)
    db.flush()

    t1 = TranscriptMessage(
        call_id=call.id,
        organization_id=test_org_a.id,
        speaker="ai",
        text="Hello Rajesh, this is an automated AI assistant calling from Apex Financial. This call is recorded for quality purposes.",
    )
    t2 = TranscriptMessage(
        call_id=call.id,
        organization_id=test_org_a.id,
        speaker="customer",
        text="I received the reminder. I will pay the full 12,500 rupees tomorrow via UPI, please send me the link.",
    )
    t3 = TranscriptMessage(
        call_id=call.id,
        organization_id=test_org_a.id,
        speaker="ai",
        text="Thank you Rajesh. I have generated your payment link and scheduled your payment commitment.",
    )
    db.add_all([t1, t2, t3])
    db.commit()

    # 10. Record Authoritative Outcome (PTP)
    outcome_resp = client.post(
        "/api/v1/recovery/outcomes",
        json={
            "call_id": str(call.id),
            "customer_id": str(customer.id),
            "account_id": str(account.id),
            "campaign_id": campaign_id,
            "outcome_type": "ptp",
            "details": {"amount": "12500.00", "promised_date": "2026-09-23T12:00:00Z"},
            "notes": "Full settlement commitment",
            "recorded_by": "ai",
        },
        headers=headers,
    )
    assert outcome_resp.status_code == 201
    outcome_id = outcome_resp.json()["data"]["id"]

    # 11. Verify Campaign Lead State
    lead_resp = client.get(f"/api/v1/campaigns/{campaign_id}/leads", headers=headers)
    assert lead_resp.status_code == 200
    leads = lead_resp.json()["items"]
    assert len(leads) == 1
    assert leads[0]["contact_state"] == "promised"
    assert leads[0]["status"] == "completed"

    # 12. Mark Queue Item Completed
    client.post(f"/api/v1/recovery/queue/{queue_item_id}/complete?completion_status=completed", headers=headers)

    # 13. Run Post-Call Analysis
    analysis_resp = client.post(f"/api/v1/calls/{call.id}/analyze", headers=headers)
    assert analysis_resp.status_code == 200
    ana_data = analysis_resp.json()["data"]
    assert ana_data["customer_intent"] == "willing_to_pay"
    assert ana_data["sentiment"] == "positive"
    assert "MISSING_AI_DISCLOSURE" not in ana_data["compliance_violations"].get("violations", [])

    # 14. Create PTP and Payment Intent
    ptp_resp = client.post(
        "/api/v1/ptp",
        json={
            "customer_id": str(customer.id),
            "account_id": str(account.id),
            "call_id": str(call.id),
            "outcome_id": outcome_id,
            "amount": "12500.00",
            "promised_date": "2026-09-23T12:00:00Z",
            "grace_period_days": 2,
        },
        headers=headers,
    )
    assert ptp_resp.status_code == 201
    ptp_id = ptp_resp.json()["data"]["id"]

    # Create Payment Intent & Send Link
    intent_resp = client.post(
        "/api/v1/payment-intents",
        json={
            "customer_id": str(customer.id),
            "account_id": str(account.id),
            "call_id": str(call.id),
            "amount": "12500.00",
            "payment_method": "payment_link",
        },
        headers=headers,
    )
    assert intent_resp.status_code == 201
    intent_id = intent_resp.json()["data"]["id"]

    send_resp = client.post(
        f"/api/v1/payment-intents/{intent_id}/send-link",
        json={"channel": "sms", "recipient": "+919876501234"},
        headers=headers,
    )
    assert send_resp.status_code == 200
    assert send_resp.json()["data"]["status"] == "link_sent"

    # 15. Customer pays via link -> Confirm payment intent
    confirm_resp = client.post(f"/api/v1/payment-intents/{intent_id}/confirm", headers=headers)
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["data"]["status"] == "confirmed"

    # 16. Reconcile PTP -> Status becomes 'kept'
    reconcile_resp = client.post(f"/api/v1/ptp/{ptp_id}/reconcile", headers=headers)
    assert reconcile_resp.status_code == 200
    assert reconcile_resp.json()["data"]["current_status"] == "kept"

    # 17. Verify Account is fully paid
    db.refresh(account)
    assert account.status == "paid"
    assert account.outstanding_amount == Decimal("0.00")

    # 18. Campaign Analytics
    analytics_resp = client.get(f"/api/v1/analytics/campaigns/{campaign_id}", headers=headers)
    assert analytics_resp.status_code == 200
    an_data = analytics_resp.json()["data"]
    assert an_data["ptp_count"] == 1
    assert Decimal(str(an_data["paid_amount"])) == Decimal("12500.00")
    assert an_data["recovery_rate"] == 100.0

    # 19. Export Job (CSV & XLSX)
    exp_resp = client.post(
        "/api/v1/exports",
        json={"export_type": "ptp", "file_format": "csv"},
        headers=headers,
    )
    assert exp_resp.status_code == 201
    export_job_id = exp_resp.json()["data"]["id"]

    # Process export
    ExportService.process_export(db, uuid.UUID(export_job_id))
    dl_resp = client.get(f"/api/v1/exports/{export_job_id}/download", headers=headers)
    assert dl_resp.status_code == 200
    assert b"12500.00" in dl_resp.content
