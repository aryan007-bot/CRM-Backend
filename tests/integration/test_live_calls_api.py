import pytest
from tests.conftest import auth_headers


def test_live_call_lifecycle_and_controls(client, supervisor_a, db):
    headers = auth_headers(supervisor_a)

    # 1. Create Customer
    cust_res = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Rohit Verma", "phones": [{"phone": "+919876543210", "is_primary": True}]},
    )
    assert cust_res.status_code == 201
    customer_id = cust_res.json()["data"]["id"]

    # 2. Initiate Call
    call_res = client.post(
        "/api/v1/live-calls",
        headers=headers,
        json={
            "customer_id": customer_id,
            "recipient_phone": "+919876543210",
        },
    )
    assert call_res.status_code == 201
    call_data = call_res.json()["data"]
    call_id = call_data["id"]
    assert call_data["status"] == "created"

    # 3. Call controls: connect, hold and resume
    conn_res = client.post(f"/api/v1/live-calls/{call_id}/resume", headers=headers)
    assert conn_res.status_code == 200
    assert conn_res.json()["data"]["status"] == "connected"

    hold_res = client.post(f"/api/v1/live-calls/{call_id}/hold", headers=headers)
    assert hold_res.status_code == 200
    assert hold_res.json()["data"]["status"] == "on_hold"

    resume_res = client.post(f"/api/v1/live-calls/{call_id}/resume", headers=headers)
    assert resume_res.status_code == 200
    assert resume_res.json()["data"]["status"] == "connected"

    # 4. Append transcript
    tx_res = client.post(
        f"/api/v1/live-calls/{call_id}/transcript",
        headers=headers,
        json={"speaker": "ai", "text": "Namaste Rohit ji, kya meri aawaz aa rahi hai?", "is_final": True},
    )
    assert tx_res.status_code == 201
    assert tx_res.json()["data"]["speaker"] == "ai"

    # 5. Human Transfer
    tr_res = client.post(
        f"/api/v1/live-calls/{call_id}/transfer",
        headers=headers,
        json={"target_extension": "sip:101@domain.local"},
    )
    assert tr_res.status_code == 200
    assert tr_res.json()["data"]["status"] == "human_connected"

    # 6. End call
    end_res = client.post(f"/api/v1/live-calls/{call_id}/end", headers=headers)
    assert end_res.status_code == 200
    assert end_res.json()["data"]["status"] == "ended"

    # 7. Invalid transition on ended call should fail
    mute_res = client.post(f"/api/v1/live-calls/{call_id}/mute", headers=headers)
    assert mute_res.status_code == 400

    # 8. Set disposition
    disp_res = client.post(
        f"/api/v1/live-calls/{call_id}/disposition",
        headers=headers,
        json={"disposition": "COMPLETED", "notes": "Customer agreed to clear dues tomorrow."},
    )
    assert disp_res.status_code == 200
    assert disp_res.json()["data"]["disposition"] == "COMPLETED"

    # 9. Verify detail endpoint has events and transcripts
    detail_res = client.get(f"/api/v1/live-calls/{call_id}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()["data"]
    assert len(detail["events"]) >= 5
    assert len(detail["transcripts"]) == 1
    assert detail["transcripts"][0]["text"] == "Namaste Rohit ji, kya meri aawaz aa rahi hai?"


def test_live_call_tenant_isolation(client, supervisor_a, org_admin_b):
    headers_a = auth_headers(supervisor_a)
    headers_b = auth_headers(org_admin_b)

    cust_res = client.post(
        "/api/v1/customers",
        headers=headers_a,
        json={"name": "Org A Customer", "phones": [{"phone": "+919999988888"}]},
    )
    customer_id = cust_res.json()["data"]["id"]

    call_res = client.post(
        "/api/v1/live-calls",
        headers=headers_a,
        json={"customer_id": customer_id, "recipient_phone": "+919999988888"},
    )
    call_id = call_res.json()["data"]["id"]

    # Org B cannot access Org A call
    b_res = client.get(f"/api/v1/live-calls/{call_id}", headers=headers_b)
    assert b_res.status_code == 404
