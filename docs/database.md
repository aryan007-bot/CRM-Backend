# Database Schema & Migrations

## Overview
PostgreSQL database managed with SQLAlchemy 2.x Declarative Models and Alembic migrations.

## Entity Relationship Overview
- `organizations`: Root tenant container (`id`, `name`, `slug`, `status`).
- `users`: User identity scoped per organization (`id`, `organization_id`, `email`, `password_hash`).
- `roles` & `user_roles`: RBAC roles linked to users.
- `customers`: Debtors and clients (`organization_id`, `name`, `email`, `status`).
- `customer_phones`: Contact numbers with preserved raw and normalized `+91` formats.
- `creditors`: Lending institutions / banks (`organization_id`, `name`, `status`).
- `accounts`: Debts assigned to customers (`customer_id`, `creditor_id`, `account_number`, `outstanding_amount`).
- `account_payments`: Historical ledger of payments recorded against accounts.
- `imports` & `import_rows`: Batch import metadata and parsed row logs with status.
- `campaigns` & `campaign_leads`: Outbound dialing configurations and debtor account lead assignments.
- `audit_logs`: Immutable audit trails for all operations.

## Running Migrations
```bash
# Upgrade to latest migration
alembic upgrade head

# Generate a new migration
alembic revision --autogenerate -m "description"
```
