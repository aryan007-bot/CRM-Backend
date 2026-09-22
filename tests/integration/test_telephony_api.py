import pytest
from tests.conftest import auth_headers


def test_telephony_and_ai_status(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    # Telephony status
    tel_res = client.get("/api/v1/telephony/status", headers=headers)
    assert tel_res.status_code == 200
    tel_data = tel_res.json()["data"]
    assert "asterisk_status" in tel_data
    assert "gateways_online" in tel_data

    # AI status
    ai_res = client.get("/api/v1/ai/status", headers=headers)
    assert ai_res.status_code == 200
    ai_data = ai_res.json()["data"]
    assert ai_data["overall_status"] == "HEALTHY"
    service_types = [s["service_type"] for s in ai_data["services"]]
    assert "STT" in service_types
    assert "LLM" in service_types
    assert "TTS" in service_types
    assert "VAD" in service_types


def test_gateway_registration_and_heartbeat(client, supervisor_a, org_admin_b):
    headers_a = auth_headers(supervisor_a)
    headers_b = auth_headers(org_admin_b)

    create_res = client.post(
        "/api/v1/telephony/gateways",
        headers=headers_a,
        json={
            "name": "SIM Gateway Delhi-1",
            "gateway_type": "GSM",
            "host": "192.168.1.105",
            "port": 5060,
        },
    )
    assert create_res.status_code == 201
    gw_id = create_res.json()["data"]["id"]

    # Record heartbeat
    hb_res = client.post(
        f"/api/v1/telephony/gateways/{gw_id}/heartbeat",
        headers=headers_a,
        json={"signal_strength": 92, "network_operator": "Jio 5G", "active_channels": 2},
    )
    assert hb_res.status_code == 200
    assert hb_res.json()["data"]["signal_strength"] == 92
    assert hb_res.json()["data"]["network_operator"] == "Jio 5G"

    # Org B cannot access Org A's gateway
    get_b = client.get(f"/api/v1/telephony/gateways/{gw_id}", headers=headers_b)
    assert get_b.status_code == 404
