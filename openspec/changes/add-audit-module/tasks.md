# Tasks: Add Audit Module

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 900-1,200; slices 180-320 |
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

| Unit | Goal / dependency | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Persistence, migration, trigger; none | PR 1 | `.\.venv\Scripts\python.exe -m pytest tests/modules/audit/test_model.py tests/alembic/test_audit_migration.py tests/integration/test_audit_postgres.py -k "migration or immutable"` | Disposable PostgreSQL upgrade/downgrade and mutation rejection | Revert audit model/enums, migration, metadata wiring, and persistence tests |
| 2 | Query service/API; after 1 | PR 2 | `.\.venv\Scripts\python.exe -m pytest tests/modules/audit/test_service.py tests/modules/audit/test_router.py` | HTTPX list/detail, filters, pagination, owner isolation, 404 | Revert audit schemas/service/router, main wiring, and read tests |
| 3 | Payment outcomes and rollback; after 2 | PR 3 | `.\.venv\Scripts\python.exe -m pytest tests/modules/payments/test_service.py tests/integration/test_audit_postgres.py -k payment` | HTTPX/PostgreSQL create, process, cancel success/replay/rejection/rollback | Revert payment service audit hooks and payment audit tests |
| 4 | Reconciliation outcomes and races; after 3 | PR 4 | `.\.venv\Scripts\python.exe -m pytest tests/modules/reconciliation/test_service.py tests/integration/test_audit_postgres.py -k reconciliation` | Two PostgreSQL sessions for ingest/reconcile replay, conflict, and isolation | Revert reconciliation hooks and reconciliation audit tests |

## Phase 1: Persistence and immutability (PR 1, <=320 lines)
- [x] 1.1 RED: test enums, model constraints, users FK, allowlisted JSON, UTC default, indexes, and UPDATE/DELETE rejection.
- [x] 1.2 GREEN: create `app/modules/audit/{enums,model}.py` and `alembic/versions/a7d3c2e9f1b6_add_audit_events.py`; wire `alembic/env.py` metadata.
- [x] 1.3 REFACTOR: name constraints/indexes, make downgrade remove trigger/function/table/enums, and keep the database surface append-only.

## Phase 2: Read-only discovery (PR 2, <=280 lines)
- [x] 2.1 RED: test owner scoping, deterministic pagination, action/resource/outcome/UTC filters, unknown/foreign `404`, no write route.
- [x] 2.2 GREEN: create `schema.py`, `service.py`, `router.py`, `exceptions.py`; register `GET /audit-events` routes in `app/main.py`.
- [x] 2.3 REFACTOR: centralize response mapping and query ordering; reject unsupported resource combinations without leaking rows.

## Phase 3: Payment integration (PR 3, <=260 lines)
- [ ] 3.1 RED: test create/process/cancel success, replay, business failure reason, atomic commit, post-rollback durability, and unaudited provider exceptions.
- [ ] 3.2 GREEN: modify `app/modules/payments/service.py` to stage success events and persist known failures in a new transaction.
- [ ] 3.3 REFACTOR: preserve processing claims, ledger behavior, and existing API responses while sharing audit transaction helpers.

## Phase 4: Reconciliation integration (PR 4, <=260 lines)
- [ ] 4.1 RED: test ingest/replay/conflict, matched/mismatched/unmatched/replay execution, races, atomic success, durable failure, and isolation.
- [ ] 4.2 GREEN: modify `app/modules/reconciliation/service.py` at ingest/reconcile commit and rollback boundaries.
- [ ] 4.3 REFACTOR: retain savepoint/unique-race recovery, Decimal/enum comparisons, and HTTP behavior.

## Phase 5: Final verification
- [ ] 5.1 VERIFY: run full pytest, migration cycle/trigger harness, and `.\.venv\Scripts\python.exe -c "import app.main"`.
- [ ] 5.2 VERIFY: run Ruff E/F/I and record excluded-flow coverage plus evidence-preserving rollback boundaries.


