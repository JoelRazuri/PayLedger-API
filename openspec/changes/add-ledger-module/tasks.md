# Tasks: Add Ledger Module

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 800-1,050 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 persistence -> PR 2 finalization -> PR 3 read API |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Immutable storage/migration | PR 1 -> main | .\.venv\Scripts\python.exe -m pytest tests/modules/ledger/test_model.py tests/alembic/test_ledger_migration.py | .\.venv\Scripts\alembic.exe upgrade head, inspect tables, then downgrade | Ledger models, migration, metadata import |
| 2 | Atomic payment finalization | PR 2 -> main | .\.venv\Scripts\python.exe -m pytest tests/modules/payments/test_provider.py tests/modules/payments/test_service.py tests/modules/ledger/test_service.py tests/integration/test_ledger_postgres.py | Process a sandbox success and inspect one balanced journal | Provider input and completion hook |
| 3 | Authenticated journal discovery | PR 3 -> main | .\.venv\Scripts\python.exe -m pytest tests/modules/ledger/test_schema.py tests/modules/ledger/test_router.py | Swagger owner/foreign-token journal reads | Ledger schemas, router, app registration |

## Phase 1: Immutable persistence (PR 1)

- [x] 1.1 **RED:** add tests/modules/ledger/test_model.py and tests/alembic/test_ledger_migration.py for positive amounts, unique payment/event and entry/side, fixed enums, two equal postings, UTC facts, deferred partial/unbalanced rejection, and upgrade/downgrade/upgrade.
- [x] 1.2 **GREEN:** create app/modules/ledger/{__init__,enums,model}.py, migration alembic/versions/<revision>_create_ledger_tables.py, and import metadata in alembic/env.py; add required indexes and deferred trigger/function.
- [x] 1.3 **REFACTOR/evidence:** run Unit 1 tests; manually run its migration harness before feat(ledger): add immutable journal persistence.

## Phase 2: Atomic completion (PR 2)

- [x] 2.1 **RED:** add tests/modules/payments/test_{provider,service}.py, tests/modules/ledger/test_service.py, and tests/integration/test_ledger_postgres.py for frozen ID input/no Session transaction during provider I/O, unchanged sandbox outcomes, success journal, non-success absence, local posting rollback to processing, and two-session convergence.
- [x] 2.2 **GREEN:** add app/modules/ledger/{exceptions,service}.py; change app/modules/payments/{provider,service}.py to claim/capture ID, lock/reload, flush two postings, and commit/rollback once.
- [x] 2.3 **REFACTOR/evidence:** run Unit 2 automated tests and PostgreSQL runtime harness; defer the user manual end-to-end sandbox verification to the final Phase 4 gate before closure.

## Phase 3: Read-only API (PR 3)

- [x] 3.1 **RED threat tests:** add tests/modules/ledger/test_{schema,router}.py for every GET, missing/invalid JWT 401, unknown/foreign journal/payment 404, invalid limit/offset/currency/account 422, and POST/PATCH/DELETE 405.
- [x] 3.2 **GREEN:** add app/modules/ledger/{schema,router}.py and register in app/main.py; implement owner joins, EXISTS account filter, distinct newest (occurred_at,id) ordering, and pagination.
- [x] 3.3 **REFACTOR/evidence:** run Unit 3 tests; manually verify Swagger owner and foreign-token reads plus absent mutation before feat(ledger): expose read-only journals.

## Phase 4: Closure

- [ ] 4.1 Run full pytest, ruff check app tests, import check, migration cycle, and final Swagger plus user manual end-to-end verification; record results.
- [ ] 4.2 After final verification, move the completed directory to openspec/changes/archive/YYYY-MM-DD-add-ledger-module using the latest related commit date.
