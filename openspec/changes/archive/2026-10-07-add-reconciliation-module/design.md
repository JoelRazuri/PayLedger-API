# Design: Add Reconciliation Module

## Technical Approach

Add a synchronous `reconciliation` feature using the existing model/schema/service/router pattern and direct SQLAlchemy. PostgreSQL owns uniqueness; services own transactions, owner scoping, snapshot calculation, and UTC response normalization. No repository or provider adapter is introduced.

## Architecture Decisions

| Decision | Choice and rationale | Rejected alternative |
|---|---|---|
| Storage | Two append-only models: independent evidence and immutable attempts; copied values preserve history. | Recomputing results from mutable Payments. |
| Vocabulary | Reuse `PaymentProvider`, `Currency`, and `PaymentStatus`; validate external status as terminal and add `ReconciliationResult`. | Duplicate/unbounded strings. |
| Evidence replay | `ExternalTransactionCreate` rejects timezone-naive `occurred_at`; offset-aware input is normalized to UTC before SHA-256 canonical JSON, persistence, and response. The fingerprint uses trimmed provider IDs, fixed-two-decimal amount, enum values, and UTC RFC3339 microseconds. Unique owner/provider/external ID selects replay versus conflict. | Server-local interpretation, payload comparison, or global identity. |
| Attempt idempotency | Unique owner/`Idempotency-Key`; same external ID replays, another external ID conflicts. New keys append. | One attempt per evidence. |
| Concurrency | Pre-read, then `flush()` inside a savepoint. Catch only the named unique constraint via PostgreSQL diagnostics, reload, and compare; rollback and re-raise every unrelated `IntegrityError`. Commit once. | Check-then-insert or broad exception recovery. |
| Matching | Select by owner/provider/non-null provider payment ID. Database uniqueness makes the match deterministic. Exact Decimal/enum comparisons set flags and result. | PayLedger ID, fuzzy, recipient, or date matching. |
| HTTP | Preserve Spanish validation/error style, authenticated dependencies, and direct router-to-service calls. | New middleware/repository abstraction. |
| Time/order | Normalize timestamps with `astimezone(UTC)` before every response; order by time DESC, ID DESC. | Driver/session-time-zone-dependent output. |

## Data Model and Flow

`external_transactions`: `id`, `owner_id` FK users RESTRICT, `provider`, `external_id` (255), `provider_payment_id` (255), `request_fingerprint` (64), `amount NUMERIC(18,2)`, `currency`, `status`, `occurred_at TIMESTAMPTZ`, `received_at TIMESTAMPTZ` default UTC now; positive-amount and terminal-status (`completed|rejected|failed|cancelled`) checks; unique `(owner_id,provider,external_id)`; index `(owner_id,received_at,id)`.

`reconciliations`: `id`, `owner_id` FK users RESTRICT, `external_transaction_id` FK RESTRICT, nullable `payment_id` FK RESTRICT, `idempotency_key` (255), external amount/currency/status, nullable local amount/currency/status, `result`, nullable three match booleans, `reconciled_at TIMESTAMPTZ` default UTC now; unique `(owner_id,idempotency_key)`; index `(owner_id,reconciled_at,id)` and `(owner_id,result,reconciled_at,id)`. Checks require positive amounts, unmatched to have null payment/local fields/flags, matched/mismatched to have all populated, matched all true, and mismatched at least one false. Services expose no mutation path.

```text
JWT -> owned evidence -> unique payment match -> snapshot/flags -> savepoint insert -> commit
```

## Interfaces and HTTP

Schemas: `ExternalTransactionCreate/Response/ListQuery`, `ReconciliationResponse/ListQuery`; a Pydantic validator requires `occurred_at.tzinfo` and non-null `utcoffset()`, otherwise `422`. List bounds are `limit=20` (1..100), `offset=0`; reconciliation accepts optional `result=matched|mismatched|unmatched`. Routes: `POST/GET /external-transactions`, `GET /external-transactions/{id}`, `POST /external-transactions/{id}/reconcile` (required `Idempotency-Key`, 1..255), `GET /reconciliations`, `GET /reconciliations/{id}`. Creates return `201`; exact replays `200`. Domain not-found maps to `404`; evidence-payload or key-ownership conflicts to `409`; FastAPI/auth preserve `422`/`401`; absent PATCH/PUT/DELETE routes produce `405`.

## File Changes

| Action | Paths |
|---|---|
| Create | `app/modules/reconciliation/{__init__,enums,model,schema,exceptions,service,router}.py`; `alembic/versions/<revision>_add_reconciliation.py`; `tests/modules/reconciliation/{__init__,test_model,test_schema,test_service,test_router}.py`; `tests/integration/test_reconciliation_postgres.py`; `tests/alembic/test_reconciliation_migration.py` |
| Modify | `app/modules/payments/model.py`; `app/main.py`; `alembic/env.py` |
| Delete | None |

## Testing Strategy

Strict RED -> GREEN -> REFACTOR with `.\.venv\Scripts\python.exe -m pytest`. Unit tests cover fingerprints, result/null rules, owner-scoped SQL, ordering, named-constraint handling, timezone-naive rejection, and non-UTC-offset normalization before fingerprint/storage. Router/API tests cover every endpoint/status/filter/bound/method and UTC `Z` responses. Disposable real PostgreSQL tests prove checks/FKs/partial uniqueness, duplicate migration preflight, two-session evidence and attempt races, replay/conflict, snapshots, UTC round-trip, and downgrade/upgrade. Run full regression and import check; manually obtain JWT, create/process Payment, ingest/replay evidence, reconcile/replay/rerun, filter/read, and record responses plus persisted counts.

## Threat Matrix

| Boundary | Applicability and safe/failure behavior | Planned RED tests |
|---|---|---|
| HTTP routing | Applicable: JWT gates every route; foreign/unknown IDs hide as `404`; invalid bodies/status/filter/bounds, including timezone-naive occurrence time, are `422`; mutations are `405` and immutable. | Parameterize all six routes for missing/invalid JWT; foreign member/reconcile IDs; timezone-naive `occurred_at` rejection; `-03:00` normalization to UTC; invalid status/result/limit/offset; PATCH/PUT/DELETE collection/member with before/after rows. |
| Documentation-like paths | N/A: no classifier/executor. | None |
| Git repository selection | N/A: no VCS boundary. | None |
| Commit state | N/A: no index/worktree operation. | None |
| Push state | N/A: no ref resolution. | None |
| PR commands | N/A: no shell/PR automation. | None |

## Migration / Rollout

Migration first queries grouped non-null Payment references and aborts with owner/provider/reference/count details if duplicates exist. Then create the result enum, evidence table, attempts table, their indexes, and partial unique index `uq_payments_owner_provider_provider_payment_id` with `WHERE provider_payment_id IS NOT NULL`; import metadata, then register the router. Downgrade drops the Payments index, attempt indexes/table, evidence index/table, then enum. Use a disposable PostgreSQL database for cycle tests; rollback removes routes before downgrade and requires evidence export.

## Open Questions

None.
