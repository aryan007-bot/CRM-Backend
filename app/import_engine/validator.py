import uuid
from typing import Any, Dict, List, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.import_engine.mapper import map_row
from app.import_engine.normalizer import normalize_date, normalize_money, normalize_phone


def validate_import_rows(
    db: Session,
    organization_id: uuid.UUID,
    raw_rows: List[Dict[str, Any]],
    mapping: Dict[str, str],
) -> Tuple[Dict[str, int], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Validates all rows in an import against format requirements, in-file duplicates, and DB duplicates.
    Returns (summary, errors, warnings, processed_rows).
    """
    total_rows = len(raw_rows)
    valid_rows_count = 0
    invalid_rows_count = 0
    duplicate_rows_count = 0

    errors: List[Dict[str, Any]] = []
    warnings: List[str] = []
    processed_rows: List[Dict[str, Any]] = []

    # Query existing accounts in organization for duplicate checking
    existing_acc_query = select(Account.account_number).where(
        Account.organization_id == organization_id
    )
    db_existing_accounts: Set[str] = set(db.scalars(existing_acc_query).all())

    # In-file duplicate tracking
    seen_file_accounts: Set[str] = set()

    for idx, raw_row in enumerate(raw_rows, start=1):
        mapped = map_row(raw_row, mapping)
        row_errors: List[Dict[str, Any]] = []
        is_duplicate = False

        # 1. Validate Customer Name
        customer_name = mapped.get("customer_name")
        if not customer_name or not str(customer_name).strip():
            row_errors.append({
                "row": idx,
                "field": "customer_name",
                "code": "MISSING_CUSTOMER_NAME",
                "message": "Customer name is required",
            })
        else:
            customer_name = str(customer_name).strip()

        # 2. Validate Account Number & Duplicate Check
        raw_account_num = mapped.get("account_number")
        if not raw_account_num or not str(raw_account_num).strip():
            row_errors.append({
                "row": idx,
                "field": "account_number",
                "code": "MISSING_ACCOUNT_NUMBER",
                "message": "Account number is required",
            })
            account_number = None
        else:
            account_number = str(raw_account_num).strip()
            # Check in-file duplicate
            if account_number in seen_file_accounts:
                is_duplicate = True
                row_errors.append({
                    "row": idx,
                    "field": "account_number",
                    "code": "DUPLICATE_FILE_ACCOUNT",
                    "message": f"Duplicate account number '{account_number}' within uploaded file",
                })
            else:
                seen_file_accounts.add(account_number)

            # Check DB duplicate
            if account_number in db_existing_accounts:
                is_duplicate = True
                row_errors.append({
                    "row": idx,
                    "field": "account_number",
                    "code": "DUPLICATE_DB_ACCOUNT",
                    "message": f"Account number '{account_number}' already exists in organization",
                })

        # 3. Validate Phone
        normalized_phone, phone_err = normalize_phone(mapped.get("phone"))
        if phone_err:
            row_errors.append({
                "row": idx,
                "field": "phone",
                "code": "INVALID_PHONE",
                "message": phone_err,
            })

        # 4. Validate Outstanding Amount
        normalized_amount, amount_err = normalize_money(mapped.get("outstanding_amount"))
        if amount_err:
            row_errors.append({
                "row": idx,
                "field": "outstanding_amount",
                "code": "INVALID_AMOUNT",
                "message": amount_err,
            })

        # 5. Validate Due Date (Optional)
        normalized_due_date, date_err = normalize_date(mapped.get("due_date"))
        if date_err:
            row_errors.append({
                "row": idx,
                "field": "due_date",
                "code": "INVALID_DATE",
                "message": date_err,
            })

        # Creditor and Email
        creditor_name = str(mapped.get("creditor_name")).strip() if mapped.get("creditor_name") else None
        if creditor_name and creditor_name.lower() == "nan":
            creditor_name = None

        email = str(mapped.get("email")).strip() if mapped.get("email") else None
        if email and email.lower() == "nan":
            email = None

        # Determine row status
        if is_duplicate:
            row_status = "duplicate"
            duplicate_rows_count += 1
        elif row_errors:
            row_status = "invalid"
            invalid_rows_count += 1
        else:
            row_status = "valid"
            valid_rows_count += 1

        errors.extend(row_errors)

        normalized_record = None
        if row_status == "valid":
            normalized_record = {
                "customer_name": customer_name,
                "phone": str(mapped.get("phone")).strip() if mapped.get("phone") else "",
                "normalized_phone": normalized_phone,
                "account_number": account_number,
                "outstanding_amount": str(normalized_amount),
                "due_date": normalized_due_date.isoformat() if normalized_due_date else None,
                "creditor_name": creditor_name,
                "email": email,
            }

        processed_rows.append({
            "row_number": idx,
            "raw_data": raw_row,
            "normalized_data": normalized_record,
            "status": row_status,
            "error_data": row_errors if row_errors else None,
        })

    summary = {
        "total_rows": total_rows,
        "valid_rows": valid_rows_count,
        "invalid_rows": invalid_rows_count,
        "duplicate_rows": duplicate_rows_count,
    }

    return summary, errors, warnings, processed_rows
