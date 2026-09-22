import pytest

from app.core.errors import ValidationException
from app.import_engine.mapper import map_row, suggest_column_mappings, validate_mapping


def test_suggest_column_mappings():
    detected_cols = ["Customer Name", "Phone Number", "Loan No", "Total Due", "Due Date", "Lender"]
    suggestions = suggest_column_mappings(detected_cols)

    assert suggestions["customer_name"] == "Customer Name"
    assert suggestions["phone"] == "Phone Number"
    assert suggestions["account_number"] == "Loan No"
    assert suggestions["outstanding_amount"] == "Total Due"
    assert suggestions["due_date"] == "Due Date"
    assert suggestions["creditor_name"] == "Lender"


def test_validate_mapping_valid():
    detected_cols = ["Name", "Phone", "Acc", "Bal"]
    valid_map = {
        "customer_name": "Name",
        "phone": "Phone",
        "account_number": "Acc",
        "outstanding_amount": "Bal",
    }
    # Should not raise
    validate_mapping(valid_map, detected_cols)


def test_validate_mapping_missing_required():
    detected_cols = ["Name", "Phone"]
    invalid_map = {
        "customer_name": "Name",
        "phone": "Phone",
    }
    with pytest.raises(ValidationException) as exc:
        validate_mapping(invalid_map, detected_cols)
    assert "Missing required field mappings" in str(exc.value)


def test_validate_mapping_nonexistent_column():
    detected_cols = ["Name", "Phone", "Acc", "Bal"]
    invalid_map = {
        "customer_name": "Name",
        "phone": "Phone",
        "account_number": "Acc",
        "outstanding_amount": "NonExistentColumn",
    }
    with pytest.raises(ValidationException) as exc:
        validate_mapping(invalid_map, detected_cols)
    assert "does not exist in uploaded file" in str(exc.value)


def test_map_row():
    raw_row = {"ColA": "John Doe", "ColB": "9876543210", "ColC": "ACC-1", "ColD": "5000"}
    mapping = {
        "customer_name": "ColA",
        "phone": "ColB",
        "account_number": "ColC",
        "outstanding_amount": "ColD",
        "due_date": None,
        "creditor_name": None,
        "email": None,
    }
    mapped = map_row(raw_row, mapping)
    assert mapped["customer_name"] == "John Doe"
    assert mapped["phone"] == "9876543210"
    assert mapped["account_number"] == "ACC-1"
    assert mapped["outstanding_amount"] == "5000"
    assert mapped["due_date"] is None
