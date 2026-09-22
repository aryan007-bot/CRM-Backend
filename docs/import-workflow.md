# Excel & CSV Import Workflow

## Workflow Lifecycle

```text
UPLOAD (.xlsx / .csv)
       │
       ▼
PARSER & DETECT COLUMNS
       │
       ▼
COLUMN MAPPING (Suggest & Confirm)
       │
       ▼
BATCH VALIDATION & DUPLICATE CHECK
(Phone Normalization, Currency Parsing, Date Normalization)
       │
       ▼
PREVIEW & CONFIRMATION
       │
       ▼
TRANSACTIONAL PERSISTENCE
(Customers, CustomerPhones, Creditors, Accounts)
```

## Normalization Specifications
1. **Phone Numbers**:
   - Sanitizes extra characters (spaces, hyphens, brackets, country codes).
   - Valid Indian numbers are converted to E.164 standard: `+91XXXXXXXXXX`.
   - Raw input is preserved in `customer_phones.phone`, normalized in `customer_phones.normalized_phone`.
2. **Financial Values**:
   - Strips `₹`, `Rs`, commas, and whitespace.
   - Converts strings into `Decimal(12, 2)`.
   - Rejects negative or unparseable values.
3. **Dates**:
   - Normalizes standard date formats (`YYYY-MM-DD`, `DD/MM/YYYY`, `DD-MM-YYYY`) and Excel serial floats into ISO `YYYY-MM-DD`.

## Duplicate Prevention & Idempotency
- **In-File Duplicate Detection**: Duplicated account numbers within the uploaded spreadsheet are flagged with `DUPLICATE_FILE_ACCOUNT`.
- **Database Duplicate Detection**: Accounts already registered in the organization cannot be re-imported (`DUPLICATE_DB_ACCOUNT`).
- **Confirmation Idempotency**: Calling `/api/v1/imports/{id}/confirm` on an already completed import immediately responds with `409 CONFLICT` and code `IMPORT_ALREADY_COMPLETED`, protecting database integrity.
