from app.core.config import settings
from tests.conftest import auth_headers

CSV_BODY = b"Customer Name,Phone Number,Account Number,Outstanding Amount\nTest,9876543210,ACC-1,1000\n"


def test_rejects_unsupported_extension(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    response = client.post(
        "/api/v1/imports/upload",
        headers=headers,
        files={"file": ("payload.txt", b"not a spreadsheet", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "Unsupported file format" in response.json()["error"]["message"]


def test_rejects_empty_file(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    response = client.post(
        "/api/v1/imports/upload",
        headers=headers,
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 400


def test_rejects_file_over_configured_limit(client, supervisor_a, monkeypatch):
    """The limit is enforced while streaming, not after buffering the whole file."""
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 1024)
    headers = auth_headers(supervisor_a)

    oversized = CSV_BODY + b"padding\n" * 400
    assert len(oversized) > 1024

    response = client.post(
        "/api/v1/imports/upload",
        headers=headers,
        files={"file": ("big.csv", oversized, "text/csv")},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "FILE_TOO_LARGE"


def test_upload_requires_write_role(client, viewer_a):
    response = client.post(
        "/api/v1/imports/upload",
        headers=auth_headers(viewer_a),
        files={"file": ("valid.csv", CSV_BODY, "text/csv")},
    )
    assert response.status_code == 403


def test_upload_requires_authentication(client):
    response = client.post(
        "/api/v1/imports/upload",
        files={"file": ("valid.csv", CSV_BODY, "text/csv")},
    )
    assert response.status_code == 401


def test_upload_returns_detected_columns(client, supervisor_a):
    headers = auth_headers(supervisor_a)

    response = client.post(
        "/api/v1/imports/upload",
        headers=headers,
        files={"file": ("valid.csv", CSV_BODY, "text/csv")},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["file_type"] == "csv"
    assert data["detected_columns"] == [
        "Customer Name",
        "Phone Number",
        "Account Number",
        "Outstanding Amount",
    ]
    assert data["row_count"] == 1
    # The server suggests mappings using the same alias heuristics used for
    # validation, so the client does not duplicate that logic.
    assert data["suggested_mapping"]["customer_name"] == "Customer Name"
    assert data["suggested_mapping"]["outstanding_amount"] == "Outstanding Amount"
    # Uploaded bytes are stored as parsed rows, never as a served file path.
    assert "path" not in data and "file_path" not in data
