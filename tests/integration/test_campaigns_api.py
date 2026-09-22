from tests.conftest import auth_headers


def test_campaigns_and_leads_workflow(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    # 1. Create Customer and Account
    cust_resp = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Karan Malhotra", "phones": [{"phone": "9876543210", "is_primary": True}]},
    )
    cust_id = cust_resp.json()["data"]["id"]

    acc_resp = client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "customer_id": cust_id,
            "account_number": "ACC-CAMP-001",
            "outstanding_amount": 18000.00,
            "status": "active",
        },
    )
    acc_id = acc_resp.json()["data"]["id"]

    # 2. Create Campaign
    camp_payload = {
        "name": "Q4 High Value Recovery",
        "description": "Target accounts above 15k",
        "timezone": "Asia/Kolkata",
        "calling_start_time": "09:30:00",
        "calling_end_time": "18:30:00",
        "max_attempts": 3,
        "retry_delay_minutes": 60,
        "concurrency_limit": 5,
    }
    camp_resp = client.post("/api/v1/campaigns", headers=headers, json=camp_payload)
    assert camp_resp.status_code == 201
    camp_id = camp_resp.json()["data"]["id"]
    assert camp_resp.json()["data"]["name"] == "Q4 High Value Recovery"

    # 3. Add Account as Lead
    lead_resp = client.post(
        f"/api/v1/campaigns/{camp_id}/leads",
        headers=headers,
        json={"account_ids": [acc_id], "priority": 1},
    )
    assert lead_resp.status_code == 201
    assert lead_resp.json()["data"]["added_leads"] == 1

    # 4. Attempt Adding Duplicate Lead
    dup_lead_resp = client.post(
        f"/api/v1/campaigns/{camp_id}/leads",
        headers=headers,
        json={"account_ids": [acc_id], "priority": 1},
    )
    assert dup_lead_resp.status_code == 409
    assert dup_lead_resp.json()["error"]["code"] == "DUPLICATE_LEADS"

    # 5. List Campaign Leads
    list_leads_resp = client.get(f"/api/v1/campaigns/{camp_id}/leads", headers=headers)
    assert list_leads_resp.status_code == 200
    leads_data = list_leads_resp.json()
    assert leads_data["total"] == 1
    assert leads_data["items"][0]["account_number"] == "ACC-CAMP-001"
    assert leads_data["items"][0]["customer_name"] == "Karan Malhotra"
