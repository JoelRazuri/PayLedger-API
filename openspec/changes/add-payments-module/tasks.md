# Tasks: Add Payments Module

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 1,050–1,350 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1A model/schema → PR1B migration → PR2 creation/discovery → PR3 processing → PR4 HTTP |
| Delivery / chain | auto-chain / stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|
| PR1A | Domain model and schemas | .\.venv\Scripts\python.exe -m pytest tests\modules\payments\test_model.py tests\modules\payments\test_schema.py | N/A: no database boundary | payments package and model/schema tests |
| PR1B | Reversible migration | .\.venv\Scripts\python.exe -m pytest tests\alembic\test_payments_migration.py | Reuse disposable PostgreSQL Alembic cycle | env import, revision, migration test |
| PR2 | Idempotent creation/discovery | .\.venv\Scripts\python.exe -m pytest tests\modules\payments\test_service.py | Two-session PostgreSQL key race | service and service tests |
| PR3 | Provider processing/lifecycle | .\.venv\Scripts\python.exe -m pytest tests\modules\payments\test_provider.py tests\modules\payments\test_service.py | Two-session process/cancel claim | provider, lifecycle service, tests |
| PR4 | HTTP integration | .\.venv\Scripts\python.exe -m pytest tests\modules\payments\test_router.py | HTTPX dependency overrides | router, main registration, router tests |

## Phase 1: Foundation (PR1)

- [x] 1.1 **RED**: add tests/modules/payments/test_model.py, tests/modules/payments/test_schema.py, and tests/alembic/test_payments_migration.py for Create/Invalid values/Immutability, enums, NUMERIC(18,2), owner-key uniqueness, indexes, and reversible schema.
- [x] 1.2 **GREEN**: create app/modules/payments/{__init__,enums,model,schema}.py; import metadata in alembic/env.py; add alembic/versions/<new_revision>_create_payments_table.py from b73c6cb6e54a.
- [x] 1.3 **REFACTOR**: simplify shared schema/model conversions without changing the RED scenarios.

## Phase 2: Creation and Discovery (PR2)

- [x] 2.1 **RED**: extend tests/modules/payments/test_service.py for Create, Replay, Key conflict, Independent owner keys, List, and Non-disclosure scenarios.
- [x] 2.2 **GREEN**: create app/modules/payments/{service,exceptions}.py with fingerprint/race handling, owned newest-first filters/pagination, and no mutation/deletion operations.
- [x] 2.3 **REFACTOR**: centralize owner-scoped lookup and transaction helpers; rerun the focused command.

## Phase 3: Processing (PR3)

- [x] 3.1 **RED**: add tests/modules/payments/test_provider.py and service tests for Outcomes, Concurrency, Stranded claim, Cancel, Invalid action, and Controlled results.
- [x] 3.2 **GREEN**: create app/modules/payments/provider.py protocol/sandbox adapter; add conditional claim, terminal persistence, and safe result mapping to service.py.
- [x] 3.3 **REFACTOR**: isolate provider-result mapping; prove no raw payload persists or is exposed.

## Phase 4: HTTP Integration (PR4)

- [ ] 4.1 **RED**: add tests/modules/payments/test_router.py for Unauthenticated, Create/Replay, filters, and Spanish 404/409/422 mappings including foreign process/cancel.
- [ ] 4.2 **GREEN**: create app/modules/payments/router.py, inject user/key/provider dependencies, register it in app/main.py, and expose only specified endpoints.
- [ ] 4.3 **REFACTOR**: keep FastAPI concerns in the router and services framework-free.

## Phase 5: Final Evidence

- [ ] 5.1 Run .\.venv\Scripts\python.exe -m pytest, .\.venv\Scripts\python.exe -m ruff check app tests alembic, and .\.venv\Scripts\python.exe -c "import app.main".
- [ ] 5.2 Set DATABASE_URL to a disposable PostgreSQL database; run .\.venv\Scripts\alembic.exe upgrade head, downgrade b73c6cb6e54a, then upgrade head; assert payment enums/table/indexes remove and recreate.
