from typing import Any, Dict, List, Optional

from app.core.errors import ValidationException

REQUIRED_STANDARD_FIELDS = [
    "customer_name",
    "phone",
    "account_number",
    "outstanding_amount",
]

OPTIONAL_STANDARD_FIELDS = [
    "due_date",
    "creditor_name",
    "email",
]

ALL_STANDARD_FIELDS = REQUIRED_STANDARD_FIELDS + OPTIONAL_STANDARD_FIELDS

# Common aliases for suggestion heuristics
FIELD_ALIASES = {
    "customer_name": [
        "customer_name", "customer", "customer name", "client", "client name",
        "name", "borrower", "debtor", "full name", "account holder",
    ],
    "phone": [
        "phone", "mobile", "contact", "phone number", "mobile number",
        "contact number", "tel", "cell", "primary phone",
    ],
    "account_number": [
        "account_number", "account", "account no", "acc no", "acc_no",
        "loan_number", "loan no", "loan id", "account id", "reference",
    ],
    "outstanding_amount": [
        "outstanding_amount", "amount", "outstanding", "balance", "due amount",
        "principal", "current balance", "total due", "debt amount",
    ],
    "due_date": [
        "due_date", "due date", "duedate", "expiry date", "payment due",
    ],
    "creditor_name": [
        "creditor_name", "creditor", "lender", "bank", "client org", "institution",
    ],
    "email": [
        "email", "email address", "mail",
    ],
}


def suggest_column_mappings(detected_columns: List[str]) -> Dict[str, Optional[str]]:
    """Generates suggested mappings between standard fields and detected file columns."""
    suggestions: Dict[str, Optional[str]] = {f: None for f in ALL_STANDARD_FIELDS}

    normalized_cols = {col.lower().replace("_", " ").strip(): col for col in detected_columns}

    for std_field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            clean_alias = alias.lower().replace("_", " ").strip()
            if clean_alias in normalized_cols:
                suggestions[std_field] = normalized_cols[clean_alias]
                break

    return suggestions


def validate_mapping(mapping: Dict[str, str], detected_columns: List[str]) -> None:
    """Ensures all required standard fields are mapped to valid existing columns."""
    missing_required = [f for f in REQUIRED_STANDARD_FIELDS if not mapping.get(f)]
    if missing_required:
        raise ValidationException(
            f"Missing required field mappings: {', '.join(missing_required)}"
        )

    for std_field, file_col in mapping.items():
        if file_col and file_col not in detected_columns:
            raise ValidationException(
                f"Mapped column '{file_col}' for '{std_field}' does not exist in uploaded file."
            )


def map_row(raw_row: Dict[str, Any], mapping: Dict[str, str]) -> Dict[str, Any]:
    """Maps raw row fields into standard schema keys."""
    mapped: Dict[str, Any] = {}
    for std_field in ALL_STANDARD_FIELDS:
        file_col = mapping.get(std_field)
        if file_col and file_col in raw_row:
            mapped[std_field] = raw_row[file_col]
        else:
            mapped[std_field] = None
    return mapped
