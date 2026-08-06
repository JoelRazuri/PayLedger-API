# Proposal: Add Payments Module

## Intent

Add an authenticated module for controlling outgoing payment instructions
without moving real money. Users need ownership, recipient history, idempotent
creation, controlled processing, and simulated outcomes before related modules.

## Scope

### In Scope

- Create ARS/USD payments for an immutable recipient snapshot, positive amount
  with at most two decimals, and a simulated provider (`mercado_pago`, `uala`, or
  `stripe`).
- Require JWT ownership and a per-user `Idempotency-Key`; replay identical
  requests and reject conflicting payloads with `409`.
- List and read owned payments with limit/offset pagination, status, provider,
  and currency filters, newest-first ordering, and `404` for foreign identifiers.
- Process pending payments through a synchronous sandbox adapter and explicit
  `success`, `business_rejection`, or `technical_failure` scenarios; cancel only
  pending payments.
- Persist lifecycle and safe metadata without deletion or raw provider payloads.

### Out of Scope

- Real money movement, production providers, webhooks, workers, FX, and
  provider-specific validation.
- Admin roles, date filters, processing recovery, ledger, reconciliation, and
  audit.

## Capabilities

### New Capabilities

- `payment-instructions`: Owned payment creation, idempotency, querying,
  controlled lifecycle actions, concurrency, and simulated provider outcomes.

### Modified Capabilities

- None.

## Approach

Create a `payments` feature whose service owns domain rules and whose router
maps domain exceptions to Spanish HTTP responses. Persist payments
with `NUMERIC`, closed enums, creator ownership, recipient snapshot, timestamps,
nullable provider ID, and controlled failure fields. Atomically commit
`pending -> processing` before calling the adapter; a concurrent attempt returns
`409`, and terminal states (`completed`, `rejected`, `failed`, `cancelled`) never
transition again. Expose `POST /payments`, `GET /payments`,
`GET /payments/{id}`, `POST /payments/{id}/process`, and
`POST /payments/{id}/cancel`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/modules/payments/` | New | Domain, persistence, adapter, and HTTP API |
| `app/main.py` | Modified | Register payments router |
| `alembic/versions/` | New | Payments schema migration |
| `tests/modules/payments/` | New | Strict-TDD behavior coverage |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Duplicate intent | Medium | Unique per-user idempotency key and payload comparison |
| Concurrent processing | Medium | Atomic claim committed before provider work |
| Stranded processing state | Medium | Document recovery gap and defer reconciliation |

## Rollback Plan

Remove the module and tests, unregister its router, and downgrade the migration.

## Dependencies

- Existing JWT current-user dependency and PostgreSQL transactional guarantees.

## Success Criteria

- [ ] Authenticated users can create, list, read, process, and cancel only their
  own payments with the defined validation, pagination, and lifecycle rules.
- [ ] Idempotent replay, conflicting keys, foreign IDs, and concurrent processing
  produce the specified safe responses.
- [ ] Simulated outcomes persist only controlled metadata; tests, Ruff,
  migrations, and application import succeed.
