# Phase 1 Backend Architecture

## Overview
Phase 1 implements a modular, multi-tenant recovery agency CRM and campaign management foundation.

```
Next.js Frontend (React / Tailwind)
              │
              │ HTTPS / JSON (JWT Bearer)
              ▼
FastAPI Application (app/main.py)
  ├── Global Middleware (Request ID, Logging, CORS, Error Formatting)
  ├── Authentication & RBAC (Bearer JWT, Organization Scoping)
  ├── API Routers (v1: auth, dashboard, customers, accounts, creditors, imports, campaigns, profile)
  └── Services & Import Engine
              │
        SQLAlchemy 2.x
              │
              ▼
PostgreSQL Database (14 Tables, Multi-Tenant via organization_id)
```

## Multi-Tenancy & Isolation
- Every record is tagged with an `organization_id` foreign key.
- Route dependency `get_current_user` extracts the authenticated user and their active organization.
- All service queries explicitly enforce `Model.organization_id == current_user.organization_id`.
- Users cannot read, mutate, or query another tenant's data.

## Role-Based Access Control (RBAC)
- **SUPER_ADMIN**: Full system access across organizations.
- **ORG_ADMIN**: Full access to all records in their organization, including deletions.
- **SUPERVISOR**: Access to CRM mutations, campaign management, and file imports.
- **AI_MANAGER**: CRM and campaign management permissions.
- **AGENT**: Operational read access to customers, accounts, and campaign details.
- **VIEWER**: Read-only access to CRM data.

## Phase 2 Boundary
Asterisk PBX, SIP trunking, GSM gateways, STT, TTS, LLM agents, dialer workers, and WebRTC calling are strictly deferred to Phase 2.
