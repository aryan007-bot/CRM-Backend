import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import (
    ActiveCallExistsException,
    GatewayNotRegisteredException,
    InvalidStateTransitionException,
    TelephonyUnavailableException,
)
from app.db.models.call import Call
from app.db.models.customer import Customer, CustomerPhone
from app.db.models.organization import Organization
from app.db.models.telephony import TelephonyGateway
from app.db.models.user import User
from app.schemas.call import CallCreate
from app.services.live_calls import LiveCallService
from app.services.telephony_core.outbound_dial_service import OutboundDialService
from app.services.telephony_core.phone_number_service import PhoneNumberService
from app.services.telephony_core.preflight_service import TelephonyPreflightService
from tests.conftest import auth_headers


def test_phone_number_normalization():
    # 1. 10-digit Indian number
    ok, norm, err = PhoneNumberService.normalize_phone("9213960958")
    assert ok is True
    assert norm == "+919213960958"
    assert err is None

    # 2. Leading zero
    ok, norm, err = PhoneNumberService.normalize_phone("09213960958")
    assert ok is True
    assert norm == "+919213960958"

    # 3. Already E.164
    ok, norm, err = PhoneNumberService.normalize_phone("+919213960958")
    assert ok is True
    assert norm == "+919213960958"

    # 4. Formatted with dashes / spaces
    ok, norm, err = PhoneNumberService.normalize_phone("+91 92139-60958")
    assert ok is True
    assert norm == "+919213960958"

    # 5. Invalid
    ok, norm, err = PhoneNumberService.normalize_phone("123")
    assert ok is False
    assert err is not None

    # 6. Masking
    masked = PhoneNumberService.mask_phone("+919213960958")
    assert masked == "+91921***958"


def test_outbound_dial_string_resolution():
    dial_str = OutboundDialService.get_outbound_dial_string("+919213960958", gateway_type="GSM", trunk_name="gsm-gateway")
    assert dial_str == "PJSIP/+919213960958@gsm-gateway"

    # Caller ID resolution
    ok, cid, _ = OutboundDialService.resolve_caller_id("+911145678900", gateway_type="GSM")
    assert ok is True
    assert cid == "+911145678900"


def test_telephony_preflight_blocks_when_unregistered(db: Session, test_org_a: Organization):
    customer = Customer(
        organization_id=test_org_a.id,
        name="Test Preflight Debtor",
        status="active",
    )
    db.add(customer)
    db.commit()

    # Preflight in LIVE mode when no Asterisk/GSM gateway is available
    preflight = TelephonyPreflightService.run_preflight(
        db=db,
        organization_id=test_org_a.id,
        customer_id=customer.id,
        recipient_phone="9213960958",
        caller_phone="+911145678900",
        mode="LIVE",
    )
    assert preflight["ready"] is False
    assert preflight["error_code"] in ("ASTERISK_UNAVAILABLE", "GSM_GATEWAY_NOT_REGISTERED")

    # In SIMULATION mode, hardware checks pass
    preflight_sim = TelephonyPreflightService.run_preflight(
        db=db,
        organization_id=test_org_a.id,
        customer_id=customer.id,
        recipient_phone="9213960958",
        caller_phone="+911145678900",
        mode="SIMULATION",
    )
    assert preflight_sim["ready"] is True
    assert preflight_sim["normalized_phone"] == "+919213960958"


def test_live_call_service_prevents_ai_speaking_before_connect(
    db: Session,
    test_org_a: Organization,
    org_admin_a: User,
):
    import asyncio

    async def _run_test():
        customer = Customer(organization_id=test_org_a.id, name="State Invariant Debtor", status="active")
        db.add(customer)
        db.commit()

        payload = CallCreate(
            customer_id=customer.id,
            recipient_phone="+919213960958",
            caller_phone="+911145678900",
            mode="SIMULATION",
        )
        call = await LiveCallService.create_call(db, test_org_a.id, org_admin_a.id, payload)
        assert call.telephony_status == "DIALING"
        assert call.ai_state == "IDLE"

        # Transition to ringing
        await LiveCallService.transition_state(db, test_org_a.id, call.id, "ringing")
        assert call.telephony_status == "RINGING"
        assert call.ai_state == "WAITING_FOR_CUSTOMER"

        # Transition to connected
        await LiveCallService.transition_state(db, test_org_a.id, call.id, "connected")
        assert call.telephony_status == "CONNECTED"
        assert call.media_state == "CONNECTED"
        assert call.ai_state == "LISTENING"

        # Now AI can speak
        await LiveCallService.transition_state(db, test_org_a.id, call.id, "ai_talking")
        assert call.ai_state == "SPEAKING"

    asyncio.run(_run_test())


def test_telephony_diagnostics_api(client: TestClient, org_admin_a: User):
    headers = auth_headers(org_admin_a)
    res = client.get("/api/v1/telephony/diagnostics", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert "ready" in data
    assert "asterisk" in data
    assert "gateway" in data
    assert "outbound_route" in data
    assert "gsm" in data


def test_telephony_test_call_endpoint(client: TestClient, org_admin_a: User):
    headers = auth_headers(org_admin_a)
    res = client.post(
        "/api/v1/telephony/test-call",
        headers=headers,
        json={
            "destination_phone": "9213960958",
            "caller_phone": "+911145678900",
            "mode": "SIMULATION",
        },
    )
    assert res.status_code == 201
    call_data = res.json()["data"]
    assert "call_id" in call_data
    assert call_data["recipient_phone"] == "+91921***958"
    assert call_data["telephony_status"] in ("ORIGINATING", "DIALING")

    # Diagnostic inspection
    diag_res = client.get(f"/api/v1/telephony/calls/{call_data['call_id']}/diagnostics", headers=headers)
    assert diag_res.status_code == 200
    diag = diag_res.json()["data"]
    assert diag["mode"] == "SIMULATION"
    assert "telephony_status" in diag
    assert "ai_state" in diag
    assert "media_state" in diag
