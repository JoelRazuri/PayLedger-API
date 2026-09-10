# Tasks: Add Reconciliation Module

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 850-1,050 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 -> PR 2 -> PR 3 -> PR 4 |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Enums, models, constraints, migration, payment-reference index | PR 1 | `.\\.venv\\Scripts\\python.exe -m pytest tests/modules/reconciliation/test_model.py tests/alembic/test_reconciliation_migration.py` | Disposable PostgreSQL upgrade/downgrade and constraints | Revert models/migration and Payments index |
| 2 | Evidence validation, fingerprinting, ingestion, replay/conflict, CRUD HTTP | PR 2 | `.\\.venv\\Scripts\\python.exe -m pytest tests/modules/reconciliation/test_schema.py tests/modules/reconciliation/test_service.py tests/modules/reconciliation/test_router.py -k evidence` | HTTPX: terminal ingest, replay, conflict, progressive rejection | Revert evidence schema/service/router/tests |
| 3 | Matching, immutable attempts, snapshots, filters, idempotent reconcile | PR 3 | `.\\.venv\\Scripts\\python.exe -m pytest tests/modules/reconciliation/test_service.py tests/modules/reconciliation/test_router.py -k reconcile` | HTTPX: matched, mismatched, unmatched, rerun, key reuse | Revert reconciliation action/service/tests |
| 4 | App wiring and PostgreSQL concurrency/UTC/regression evidence | PR 4 | `.\\.venv\\Scripts\\python.exe -m pytest tests/integration/test_reconciliation_postgres.py tests/modules/reconciliation/test_router.py` | Two-session races plus manual JWT/payment/evidence/reconcile walkthrough | Revert `app/main.py`, `alembic/env.py`, wiring tests |

## Phase 1: Foundation (PR 1)

- [x] 1.1 RED: failing model/migration tests for enums, positive/status checks, FK RESTRICT, uniqueness/indexes, unmatched null rules, and Payments partial reference uniqueness.
- [x] 1.2 GREEN: create `app/modules/reconciliation/{__init__,enums,model}.py` and Alembic revision with duplicate preflight, tables, constraints, indexes, enum, reversible downgrade; modify `app/modules/payments/model.py`.
- [x] 1.3 REFACTOR: align typed mappings, constraint names, metadata imports, and migration tests with repository conventions.

> Correction evidence (2026-09-10): matched/mismatched attempts now require a non-null `local_amount`; ORM metadata and the disposable PostgreSQL migration harness reject its omission.

## Phase 2: Evidence API (PR 2)

- [x] 2.1 RED: tests across all six routes for missing/invalid JWT (401), progressive/malformed/timezone-naive payload (422), foreign/unknown IDs (404), and PATCH/PUT/DELETE immutability (405).
- [x] 2.2 RED: tests for `-03:00` UTC normalization, terminal timestamps, fingerprint replay, changed payload 409, and concurrent owner/provider/external uniqueness.
- [x] 2.3 GREEN: implement `schema.py`, `exceptions.py`, `service.py`, and evidence `router.py` routes with validation, UTC responses, owner scoping, named-constraint recovery.
- [x] 2.4 REFACTOR: preserve Spanish errors, deterministic pagination/order, and endpoint-focused tests.

> Evidence API verification (2026-09-10): six missing/invalid JWT cases and six forbidden collection/member mutations return 401/405; HTTPX + PostgreSQL verifies terminal ingestion, offset UTC normalization, replay, changed-payload conflict, and foreign-ID 404.

> Gatekeeper correction evidence (2026-09-10): two synchronized PostgreSQL sessions converge on one exact evidence row and one replay; HTTP rejects timezone-naïve occurrence timestamps with 422; PostgreSQL listing proves `received_at DESC, id DESC` ordering, including an equal-time ID tie.

## Phase 3: Reconciliation API (PR 3)

- [x] 3.1 RED: tests for missing `Idempotency-Key` (422), foreign/unknown reconcile IDs (404), key reuse 409, same-key replay, new-key append, and concurrent single-attempt behavior.
- [x] 3.2 RED: tests for matched flags, currency-only mismatch, unmatched null snapshots, immutable IDs, and newest-first result filtering/pagination.
- [x] 3.3 GREEN: implement reconciliation schemas, matching/snapshots, savepoint/named-constraint handling, list/detail queries, and action route.
- [x] 3.4 REFACTOR: enforce Decimal/enum comparisons, UTC normalization, and no mutation paths.

## Phase 4: Integration (PR 4)

- [ ] 4.1 RED: tests for app import/route registration, PostgreSQL races, UTC round-trip, migration cycle, and owner-isolation regression.
- [ ] 4.2 GREEN: modify `app/main.py` and `alembic/env.py`; add integration/migration tests and route wiring.
- [ ] 4.3 REFACTOR: run full pytest/import checks, record manual responses/counts, and document rollback/evidence export.
