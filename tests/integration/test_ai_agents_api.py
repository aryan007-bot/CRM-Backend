import io
import pytest
from tests.conftest import auth_headers


def test_ai_agent_lifecycle_and_voice_preview(client, supervisor_a, db):
    headers = auth_headers(supervisor_a)

    # 1. Create AI agent without voice profile -> status is DRAFT
    create_res = client.post(
        "/api/v1/ai-agents",
        headers=headers,
        json={
            "name": "Recovery Agent Amit",
            "language": "hi-IN",
            "model": "llama-3.3-70b-versatile",
            "system_prompt": "You are a polite debt recovery agent calling regarding an outstanding balance.",
            "disclosure": "I am an automated AI calling assistant from ABC Recovery.",
        },
    )
    assert create_res.status_code == 201
    agent_data = create_res.json()["data"]
    agent_id = agent_data["id"]
    assert agent_data["status"] == "DRAFT"
    assert agent_data["name"] == "Recovery Agent Amit"

    # 2. Upload voice reference audio -> status becomes READY
    dummy_wav = b"RIFF____WAVEfmt " + b"\x00" * 30 + b"data____" + b"\x00" * 200
    upload_res = client.post(
        f"/api/v1/ai-agents/{agent_id}/voice",
        headers=headers,
        files={"file": ("voice_sample.wav", io.BytesIO(dummy_wav), "audio/wav")},
    )
    assert upload_res.status_code == 201
    voice_data = upload_res.json()["data"]
    assert voice_data["status"] == "READY"

    # 3. Check agent status is now READY
    get_res = client.get(f"/api/v1/ai-agents/{agent_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["data"]["status"] == "READY"
    assert get_res.json()["data"]["voice_profile"]["id"] == voice_data["id"]

    # 4. Generate voice preview
    preview_res = client.post(
        f"/api/v1/ai-agents/{agent_id}/voice/preview",
        headers=headers,
        json={"text": "Namaste, kya aap mujhe sun sakte hain?"},
    )
    assert preview_res.status_code == 200
    preview_data = preview_res.json()["data"]
    assert "audio_base64" in preview_data
    assert preview_data["format"] == "wav"
    assert preview_data["sample_rate"] == 24000


def test_ai_agent_tenant_isolation(client, supervisor_a, org_admin_b):
    headers_a = auth_headers(supervisor_a)
    headers_b = auth_headers(org_admin_b)

    create_res = client.post(
        "/api/v1/ai-agents",
        headers=headers_a,
        json={
            "name": "Org A Agent",
            "language": "en-IN",
            "model": "llama-3.3-70b-versatile",
            "system_prompt": "You are a professional assistant for Organization A.",
            "disclosure": "I am an AI calling on behalf of Organization A.",
        },
    )
    agent_id = create_res.json()["data"]["id"]

    # Org B cannot access Org A's agent
    b_res = client.get(f"/api/v1/ai-agents/{agent_id}", headers=headers_b)
    assert b_res.status_code == 404
