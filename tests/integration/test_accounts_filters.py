from tests.conftest import auth_headers


def _seed(client, headers):
    """Two customers, two creditors, three accounts with distinct due dates."""
    creditor_1 = client.post("/api/v1/creditors", headers=headers, json={"name": "Alpha Finance"}).json()["data"]["id"]
    creditor_2 = client.post("/api/v1/creditors", headers=headers, json={"name": "Beta Bank"}).json()["data"]["id"]

    cust_1 = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Ravi Kumar", "phones": [{"phone": "9876543210", "is_primary": True}]},
    ).json()["data"]["id"]
    cust_2 = client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Meera Nair", "phones": [{"phone": "9812345678", "is_primary": True}]},
    ).json()["data"]["id"]

    accounts = [
        {
            "customer_id": cust_1,
            "creditor_id": creditor_1,
            "account_number": "ACC-001",
            "outstanding_amount": "10000.00",
            "due_date": "2026-01-15",
            "status": "active",
        },
        {
            "customer_id": cust_1,
            "creditor_id": creditor_2,
            "account_number": "ACC-002",
            "outstanding_amount": "25000.50",
            "due_date": "2026-06-30",
            "status": "paid",
        },
        {
            "customer_id": cust_2,
            "creditor_id": creditor_1,
            "account_number": "ACC-003",
            "outstanding_amount": "5000.00",
            "due_date": "2026-03-01",
            "status": "active",
        },
    ]
    for payload in accounts:
        created = client.post("/api/v1/accounts", headers=headers, json=payload)
        assert created.status_code == 201

    return {
        "cust_1": cust_1,
        "cust_2": cust_2,
        "creditor_1": creditor_1,
        "creditor_2": creditor_2,
    }


def test_account_filters(client, supervisor_a):
    headers = auth_headers(supervisor_a)
    ids = _seed(client, headers)

    # No filter -> everything
    assert client.get("/api/v1/accounts", headers=headers).json()["total"] == 3

    # Exact customer filter
    by_customer = client.get(
        f"/api/v1/accounts?customer_id={ids['cust_1']}", headers=headers
    ).json()
    assert by_customer["total"] == 2
    assert {item["account_number"] for item in by_customer["items"]} == {"ACC-001", "ACC-002"}

    # Creditor filter
    by_creditor = client.get(
        f"/api/v1/accounts?creditor_id={ids['creditor_1']}", headers=headers
    ).json()
    assert by_creditor["total"] == 2

    # Status filter
    assert client.get("/api/v1/accounts?status=active", headers=headers).json()["total"] == 2
    assert client.get("/api/v1/accounts?status=paid", headers=headers).json()["total"] == 1

    # Due date window
    window = client.get(
        "/api/v1/accounts?due_date_from=2026-01-01&due_date_to=2026-03-31", headers=headers
    ).json()
    assert window["total"] == 2

    # Search matches account number or customer name
    assert client.get("/api/v1/accounts?search=ACC-003", headers=headers).json()["total"] == 1
    assert client.get("/api/v1/accounts?search=Meera", headers=headers).json()["total"] == 1


def test_account_pagination_and_ordering(client, supervisor_a):
    headers = auth_headers(supervisor_a)
    ids = _seed(client, headers)

    page_1 = client.get("/api/v1/accounts?page=1&page_size=2", headers=headers).json()
    assert page_1["total"] == 3
    assert len(page_1["items"]) == 2
    assert page_1["page"] == 1
    assert page_1["page_size"] == 2

    page_2 = client.get("/api/v1/accounts?page=2&page_size=2", headers=headers).json()
    assert len(page_2["items"]) == 1

    # Filters and pagination compose.
    filtered = client.get(
        f"/api/v1/accounts?customer_id={ids['cust_2']}&page=1&page_size=2",
        headers=headers,
    ).json()
    assert filtered["total"] == 1

    # Sorting by a numeric column
    sorted_amounts = client.get(
        "/api/v1/accounts?sort_by=outstanding_amount&sort_direction=asc", headers=headers
    ).json()["items"]
    assert [item["account_number"] for item in sorted_amounts] == ["ACC-003", "ACC-001", "ACC-002"]


def test_account_page_size_is_bounded(client, supervisor_a):
    headers = auth_headers(supervisor_a)
    assert client.get("/api/v1/accounts?page_size=500", headers=headers).status_code == 422
    assert client.get("/api/v1/accounts?page=0", headers=headers).status_code == 422
