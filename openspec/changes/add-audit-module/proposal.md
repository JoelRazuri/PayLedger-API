# Proposal: Add Audit Module

## Intent

Provide immutable evidence answering who performed each financial action, when, against which resource, and with what business outcome, without becoming technical logging.

## Scope

### In Scope

- Record authenticated `payment.create`, `payment.process`, `payment.cancel`, `external_transaction.ingest`, and `reconciliation.execute` attempts; idempotent replays create events with `details.replayed=true`.
- Store the JWT-derived actor, action, resource type/optional ID, outcome, failure reason, allowlisted details, and UTC occurrence time.
- Commit successful domain changes and audit events atomically; after rollback, persist authenticated business failures in a separate transaction.
- Expose owner-scoped `GET /audit-events` and `GET /audit-events/{id}` with pagination and action, resource, outcome, and UTC range filters; unknown or foreign IDs return `404`.
- Enforce append-only storage and reject `UPDATE`/`DELETE` through PostgreSQL.

### Out of Scope

- GET access logs, registration/login, malformed input, invalid/missing JWT, generic `422` validation, infrastructure/security logs, arbitrary request bodies, admin/global access, export, retention/archival, and asynchronous delivery.

## Capabilities

### New Capabilities

- `financial-audit`: Immutable event capture and owner-scoped audit discovery.

### Modified Capabilities

- `payment-instructions`: Financial mutations and authenticated business failures gain automatic audit outcomes.
- `payment-reconciliation`: External ingestion and reconciliation executions gain automatic audit outcomes.

## Approach

Add a modular Audit feature, migration, and tests. Reference `users` by foreign key; validate polymorphic resources in services without cross-table foreign keys. Use business outcomes rather than HTTP status: provider rejection/failure is `failure`, valid replay is `success`, and `reason_code` is required only for failures.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `app/modules/audit/` | New | Event persistence, queries, and read API |
| `app/modules/payments/service.py` | Modified | Atomic success and post-rollback failure capture |
| `app/modules/reconciliation/service.py` | Modified | Ingestion/reconciliation capture |
| `app/main.py`, `alembic/versions/` | Modified/New | Router registration and immutable schema |
| `tests/` | New/Modified | Domain, API, migration, and transaction coverage |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Audit gaps or false success | Medium | Define transaction boundaries and failure-path tests |
| Sensitive detail leakage | Medium | Server-owned allowlist; never store tokens or raw bodies |
| Resource ambiguity | Medium | Closed resource types and service validation |

## Rollback Plan

Unregister Audit, revert integrations/tests, and downgrade the migration. Preserve evidence if rollback follows production use.

## Dependencies

- Existing JWT identity, PostgreSQL transactions, Payments, and Reconciliation.

## Success Criteria

- [ ] Every scoped action and replay produces the correct owner-isolated success or failure event without altering excluded flows.
- [ ] Successful mutations are atomic with Audit; business failures survive domain rollback.
- [ ] Read filters, UTC timestamps, `404` non-disclosure, append-only trigger, migration, tests, Ruff, and application import pass.
