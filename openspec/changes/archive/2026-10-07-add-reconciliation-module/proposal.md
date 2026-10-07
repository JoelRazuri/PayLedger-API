# Proposal: Add Reconciliation Module

## Intent

Let owners ingest independent provider evidence and compare it with local payments. PayLedger controls/reconciles finances; it is not a bank/wallet. Discrepancies remain for Audit investigation.

## Scope

### In Scope
- A dedicated simulated API ingests immutable external operations independently. It accepts only `completed|rejected|failed|cancelled`; records provider `occurred_at` and PayLedger `received_at`; and enforces owner/provider/`external_id` uniqueness. Exact replay returns existing; conflicting payload returns `409`.
- `POST/GET /external-transactions`, `GET /external-transactions/{id}`, `POST /external-transactions/{id}/reconcile`, and `GET /reconciliations[/{id}]` require JWT, isolate owners, return `404` for foreign/unknown IDs, and list newest-first with limit/offset default20/max100. Reconciliation lists filter `matched|mismatched|unmatched`.
- Ingestion and reconciliation are separate synchronous actions. Matching uses owner+provider+provider-payment-reference, never PayLedger ID. Unmatched evidence remains persisted.
- Each deliberate rerun appends an immutable attempt: source IDs, UTC `reconciled_at`, local/external amount/currency/status snapshots, result `matched|mismatched|unmatched`, and nullable `amount_matches`, `currency_matches`, `status_matches`; local snapshots/flags are null when unmatched.
- Reconcile requires `Idempotency-Key`: same owner/key/external-operation replays, reuse for another operation returns `409`, a new key creates another attempt, and concurrency creates one.
- Automated work-unit tests, manual end-to-end verification, UTC cases, and PostgreSQL migration/concurrency/idempotency evidence.

### Out of Scope
- PATCH/DELETE or evidence correction; real adapters/webhooks; provider status mapping; progressive events; batches/queues/schedulers; manual resolution; rules; recipient/date comparisons; metrics/reports; Audit implementation.

## Capabilities

### New Capabilities
- `payment-reconciliation`: External evidence, matching, immutable attempts, owner-scoped queries, idempotency, concurrency, and UTC behavior.

### Modified Capabilities
- None. Payment-reference uniqueness supports deterministic matching without changing the Payment API.

## Approach

Build `app/modules/reconciliation` within existing boundaries. Compare only amount, currency, and canonical status. Add PostgreSQL uniqueness for external identities/attempt keys, plus a Payments partial unique index on `(owner_id,provider,provider_payment_id)` where non-null.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `app/modules/reconciliation/` | New | Module/API |
| `app/modules/payments/model.py` | Modified | Matching-support index |
| `alembic/versions/` | Modified | Database migration |
| `app/main.py` | Modified | Routes |
| `tests/` | Modified | Behavioral/database evidence |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Duplicate evidence/attempts under concurrency | Medium | Transactional database uniqueness |
| Legacy payment-reference duplicates block migration | Medium | Preflight detection |
| Decimal/time normalization causes false mismatches | Medium | Exact numerics and UTC boundary tests |

## Rollback Plan

Remove routes/code, then downgrade the migration to drop reconciliation objects and the Payments index. Export evidence before destructive rollback.

## Dependencies

- JWT ownership, Payments, PostgreSQL, SQLAlchemy, and Alembic.

## Success Criteria

- [ ] Ingestion, matching, replay/conflict, rerun, concurrency, snapshots, and unmatched retention satisfy these rules.
- [ ] Owner isolation, `404`, filters, pagination, terminal-state validation, exact comparisons, and UTC timestamps are verified.
- [ ] Automated suites and manual end-to-end verification pass with PostgreSQL evidence.
