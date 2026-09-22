# API Reference & Endpoints

Base path: `/api/v1`

## Standard Envelope Responses
- Single item: `{"data": {...}}`
- Paginated list: `{"items": [...], "page": 1, "page_size": 25, "total": 100}`
- Error format: `{"error": {"code": "RESOURCE_NOT_FOUND", "message": "Customer not found"}}`

## Key Endpoints

### Health
- `GET /health`: Liveness probe (`{"status": "ok"}`)
- `GET /ready`: Readiness probe verifying PostgreSQL connection

### Authentication
- `POST /api/v1/auth/login`: Issue JWT token
- `POST /api/v1/auth/logout`: Log out
- `GET /api/v1/auth/me`: Current user context

### Profile
- `GET /api/v1/profile`: View profile
- `PATCH /api/v1/profile`: Update name / email

### Dashboard
- `GET /api/v1/dashboard/summary`: Genuine database counts (customers, accounts, outstanding balance, active campaigns, pending imports)

### Customers
- `GET /api/v1/customers`: List with pagination and search
- `POST /api/v1/customers`: Create customer with phone numbers
- `GET /api/v1/customers/{id}`: Single customer detail
- `PATCH /api/v1/customers/{id}`: Update customer
- `DELETE /api/v1/customers/{id}`: Delete customer

### Accounts & Creditors
- `GET /api/v1/accounts`: Paginated accounts
- `POST /api/v1/accounts`: Create account
- `GET /api/v1/accounts/{id}`: Account details with payments
- `POST /api/v1/accounts/{id}/payments`: Record historical payment
- `GET /api/v1/creditors`: List creditors
- `POST /api/v1/creditors`: Create creditor

### Imports
- `POST /api/v1/imports/upload`: Upload `.xlsx` or `.csv`
- `GET /api/v1/imports`: Import history
- `GET /api/v1/imports/{id}`: Import details
- `POST /api/v1/imports/{id}/validate`: Submit column mappings and validate dataset
- `POST /api/v1/imports/{id}/confirm`: Transactional commit into database

### Campaigns
- `GET /api/v1/campaigns`: List campaigns
- `POST /api/v1/campaigns`: Create campaign
- `GET /api/v1/campaigns/{id}`: Campaign details
- `PATCH /api/v1/campaigns/{id}`: Update campaign settings
- `POST /api/v1/campaigns/{id}/leads`: Attach accounts as campaign leads
- `GET /api/v1/campaigns/{id}/leads`: List leads with pagination
