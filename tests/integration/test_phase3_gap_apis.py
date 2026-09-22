import uuid
from decimal import Decimal
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.customer import Customer, CustomerPhone
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.organization import Organization
from app.db.models.user import User
from tests.conftest import auth_headers


def test_phase3_gap_apis_e2e(
    client: TestClient,
    db: Session,
    test_org_a: Organization,
    supervisor_a: User,
):
    headers = auth_headers(supervisor_a)

    # 1. Base test data
    customer = Customer(organization_id=test_org_a.id, name="Phase 3 Debtor")
    db.add(customer)
    db.flush()

    phone = CustomerPhone(
        customer_id=customer.id,
        phone="+919876543210",
        normalized_phone="+919876543210",
        phone_type="mobile",
        is_primary=True,
    )
    db.add(phone)

    account = Account(
        organization_id=test_org_a.id,
        customer_id=customer.id,
        account_number=f"ACC-P3-{uuid.uuid4().hex[:6]}",
        outstanding_amount=Decimal("15000.00"),
        status="active",
    )
    db.add(account)
    db.commit()

    # --- PTP Endpoints ---
    ptp_resp = client.post(
        "/api/v1/ptp",
        json={
            "customer_id": str(customer.id),
            "account_id": str(account.id),
            "amount": "5000.00",
            "promised_date": "2026-11-01T10:00:00Z",
            "grace_period_days": 3,
        },
        headers=headers,
    )
    assert ptp_resp.status_code == 201
    ptp_id = ptp_resp.json()["data"]["id"]

    # GET /ptp/{id}
    get_ptp = client.get(f"/api/v1/ptp/{ptp_id}", headers=headers)
    assert get_ptp.status_code == 200
    assert get_ptp.json()["data"]["id"] == ptp_id

    # POST /ptp/{id}/confirm
    confirm_ptp = client.post(f"/api/v1/ptp/{ptp_id}/confirm", headers=headers)
    assert confirm_ptp.status_code == 200
    assert confirm_ptp.json()["data"]["status"] == "confirmed"

    # POST /ptp/{id}/cancel
    cancel_ptp = client.post(f"/api/v1/ptp/{ptp_id}/cancel", headers=headers)
    assert cancel_ptp.status_code == 200
    assert cancel_ptp.json()["data"]["status"] == "cancelled"

    # --- Callbacks Endpoints ---
    cb_resp = client.post(
        "/api/v1/callbacks",
        json={
            "customer_id": str(customer.id),
            "account_id": str(account.id),
            "phone_number": "+919876543210",
            "scheduled_time": "2026-11-02T14:30:00Z",
            "requested_by": "customer",
        },
        headers=headers,
    )
    assert cb_resp.status_code == 201
    cb_id = cb_resp.json()["data"]["id"]

    # GET /callbacks/{id}
    get_cb = client.get(f"/api/v1/callbacks/{cb_id}", headers=headers)
    assert get_cb.status_code == 200
    assert get_cb.json()["data"]["status"] == "pending"

    # POST /callbacks/{id}/complete
    complete_cb = client.post(f"/api/v1/callbacks/{cb_id}/complete", headers=headers)
    assert complete_cb.status_code == 200
    assert complete_cb.json()["data"]["status"] == "completed"

    # POST /callbacks/{id}/cancel
    cancel_cb = client.post(f"/api/v1/callbacks/{cb_id}/cancel", headers=headers)
    assert cancel_cb.status_code == 200
    assert cancel_cb.json()["data"]["status"] == "cancelled"

    # --- Disputes Endpoints ---
    disp_resp = client.post(
        "/api/v1/disputes",
        json={
            "customer_id": str(customer.id),
            "account_id": str(account.id),
            "reason_category": "already_paid",
            "dispute_details": "Paid via net banking yesterday",
        },
        headers=headers,
    )
    assert disp_resp.status_code == 201
    disp_id = disp_resp.json()["data"]["id"]

    # GET /disputes/{id}
    get_disp = client.get(f"/api/v1/disputes/{disp_id}", headers=headers)
    assert get_disp.status_code == 200

    # POST /disputes/{id}/assign
    assign_disp = client.post(
        f"/api/v1/disputes/{disp_id}/assign",
        json={"assigned_to": str(supervisor_a.id)},
        headers=headers,
    )
    assert assign_disp.status_code == 200
    assert assign_disp.json()["data"]["assigned_to"] == str(supervisor_a.id)

    # POST /disputes/{id}/resolve
    resolve_disp = client.post(
        f"/api/v1/disputes/{disp_id}/resolve",
        json={"resolution_notes": "Payment receipt verified"},
        headers=headers,
    )
    assert resolve_disp.status_code == 200
    assert resolve_disp.json()["data"]["status"] == "resolved"

    # POST /disputes/{id}/escalate
    escalate_disp = client.post(
        f"/api/v1/disputes/{disp_id}/escalate",
        json={"notes": "Needs manager verification"},
        headers=headers,
    )
    assert escalate_disp.status_code == 200
    assert escalate_disp.json()["data"]["status"] == "escalated"

    # --- Escalations Endpoints ---
    esc_resp = client.post(
        "/api/v1/escalations",
        json={
            "customer_id": str(customer.id),
            "account_id": str(account.id),
            "reason": "customer_demanded_manager",
            "priority": "high",
        },
        headers=headers,
    )
    assert esc_resp.status_code == 201
    esc_id = esc_resp.json()["data"]["id"]

    # GET /escalations/{id}
    get_esc = client.get(f"/api/v1/escalations/{esc_id}", headers=headers)
    assert get_esc.status_code == 200

    # POST /escalations/{id}/assign
    assign_esc = client.post(
        f"/api/v1/escalations/{esc_id}/assign",
        json={"escalated_to": str(supervisor_a.id)},
        headers=headers,
    )
    assert assign_esc.status_code == 200
    assert assign_esc.json()["data"]["escalated_to"] == str(supervisor_a.id)

    # POST /escalations/{id}/resolve
    resolve_esc = client.post(
        f"/api/v1/escalations/{esc_id}/resolve",
        json={"resolution_notes": "Settlement agreed"},
        headers=headers,
    )
    assert resolve_esc.status_code == 200
    assert resolve_esc.json()["data"]["status"] == "resolved"

    # POST /escalations/{id}/cancel
    cancel_esc = client.post(f"/api/v1/escalations/{esc_id}/cancel", headers=headers)
    assert cancel_esc.status_code == 200
    assert cancel_esc.json()["data"]["status"] == "dismissed"

    # --- Payment Intents Endpoints ---
    intent_resp = client.post(
        "/api/v1/payment-intents",
        json={
            "customer_id": str(customer.id),
            "account_id": str(account.id),
            "amount": "2000.00",
            "payment_method": "upi",
        },
        headers=headers,
    )
    assert intent_resp.status_code == 201
    intent_id = intent_resp.json()["data"]["id"]

    # GET /payment-intents/{id}
    get_intent = client.get(f"/api/v1/payment-intents/{intent_id}", headers=headers)
    assert get_intent.status_code == 200

    # POST /payment-intents/{id}/verify
    verify_intent = client.post(f"/api/v1/payment-intents/{intent_id}/verify", headers=headers)
    assert verify_intent.status_code == 200
    assert verify_intent.json()["data"]["status"] == "confirmed"

    # --- Recovery Endpoints (Root alias & actions) ---
    get_recovery = client.get("/api/v1/recovery", headers=headers)
    assert get_recovery.status_code == 200
    assert "items" in get_recovery.json()

    action_recovery = client.post(
        "/api/v1/recovery/actions",
        json={"action": "pause", "item_ids": []},
        headers=headers,
    )
    assert action_recovery.status_code == 200
    assert action_recovery.json()["data"]["updated"] == 0

    # --- Campaign Advanced Endpoints ---
    camp_resp = client.post(
        "/api/v1/campaigns",
        json={
            "name": "Integration Recovery Campaign",
            "campaign_type": "recovery",
            "priority": 2,
        },
        headers=headers,
    )
    assert camp_resp.status_code == 201
    camp_id = camp_resp.json()["data"]["id"]

    # Add lead
    add_leads_resp = client.post(
        f"/api/v1/campaigns/{camp_id}/leads",
        json={"account_ids": [str(account.id)]},
        headers=headers,
    )
    assert add_leads_resp.status_code == 201

    # GET /campaigns/{id}/leads
    leads_list = client.get(f"/api/v1/campaigns/{camp_id}/leads", headers=headers)
    assert leads_list.status_code == 200
    lead_id = leads_list.json()["items"][0]["id"]

    # PATCH /campaigns/{id}/leads/{lead_id}
    patch_lead = client.patch(
        f"/api/v1/campaigns/{camp_id}/leads/{lead_id}",
        json={"priority": 5},
        headers=headers,
    )
    assert patch_lead.status_code == 200
    assert patch_lead.json()["data"]["priority"] == 5

    # POST /campaigns/{id}/leads/bulk
    bulk_leads = client.post(
        f"/api/v1/campaigns/{camp_id}/leads/bulk",
        json={"action": "pause", "lead_ids": [lead_id]},
        headers=headers,
    )
    assert bulk_leads.status_code == 200
    assert bulk_leads.json()["data"]["updated"] == 1

    # POST /campaigns/leads/preview
    preview_leads = client.post(
        "/api/v1/campaigns/leads/preview",
        json={"min_outstanding": "1000.00"},
        headers=headers,
    )
    assert preview_leads.status_code == 200
    assert preview_leads.json()["data"]["stats"]["total"] >= 1

    # GET /campaigns/{id}/metrics
    metrics = client.get(f"/api/v1/campaigns/{camp_id}/metrics", headers=headers)
    assert metrics.status_code == 200
    assert metrics.json()["data"]["total_leads"] >= 1

    # GET /campaigns/{id}/distributions
    distributions = client.get(f"/api/v1/campaigns/{camp_id}/distributions", headers=headers)
    assert distributions.status_code == 200
    assert "recovery_outcomes" in distributions.json()["data"]

    # GET /campaigns/{id}/activity
    activity = client.get(f"/api/v1/campaigns/{camp_id}/activity", headers=headers)
    assert activity.status_code == 200
    assert "items" in activity.json()

    # GET /campaigns/{id}/analytics
    analytics = client.get(f"/api/v1/campaigns/{camp_id}/analytics", headers=headers)
    assert analytics.status_code == 200
    assert analytics.json()["data"]["campaign_name"] == "Integration Recovery Campaign"

    # POST /campaigns/{id}/duplicate
    duplicate = client.post(f"/api/v1/campaigns/{camp_id}/duplicate", headers=headers)
    assert duplicate.status_code == 200
    assert "(Copy)" in duplicate.json()["data"]["name"]

    # DELETE /campaigns/{id}/leads/{lead_id}
    del_lead = client.delete(f"/api/v1/campaigns/{camp_id}/leads/{lead_id}", headers=headers)
    assert del_lead.status_code == 204

    # --- Exports Preview Endpoint ---
    preview_export = client.post(
        "/api/v1/exports/preview",
        json={"export_type": "ptp", "file_format": "csv"},
        headers=headers,
    )
    assert preview_export.status_code == 200
    assert "row_count" in preview_export.json()["data"]

    # --- Follow-Ups Router ---
    list_fu = client.get("/api/v1/follow-ups", headers=headers)
    assert list_fu.status_code == 200
    assert "items" in list_fu.json()

    # --- Automation Rules Alias Router ---
    list_rules = client.get("/api/v1/automation-rules", headers=headers)
    assert list_rules.status_code == 200
    assert "items" in list_rules.json()

    # --- Call Analysis Router ---
    list_ca = client.get("/api/v1/call-analysis", headers=headers)
    assert list_ca.status_code == 200
    assert "items" in list_ca.json()
