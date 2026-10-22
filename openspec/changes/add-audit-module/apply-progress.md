# Apply Progress: Add Audit Module
## Completed Tasks
- [x] 1.1 RED: persistence and immutability tests
- [x] 1.2 GREEN: audit persistence model and migration
- [x] 1.3 REFACTOR: named database surface and reversible immutability
- [x] 2.1 RED: owner-scoped discovery API tests
- [x] 2.2 GREEN: query schemas, service, router, and application registration
- [x] 2.3 REFACTOR: centralized ordering, mapping, and safe filter validation
- [x] 3.1 RED: payment audit integration tests
- [x] 3.2 GREEN: atomic payment audit staging and failure persistence
- [x] 3.3 REFACTOR: shared allowlisted audit helpers and preserved lifecycle commits
- [x] 4.1 RED: reconciliation audit behavior tests
- [x] 4.2 GREEN: atomic reconciliation audit integration
- [x] 4.3 REFACTOR: preserve races, comparisons, and HTTP behavior

## TDD Cycle Evidence
| Task | RED | GREEN | REFACTOR |
|---|---|---|---|
| 1.1 | `pytest tests/modules/audit/test_model.py tests/alembic/test_audit_migration.py` failed during collection: `ModuleNotFoundError: app.modules.audit.enums` | Final focused run: 2 passed | Assertions retain closed values, FK, checks, indexes, and UTC defaults |
| 1.2 | Migration/model tests were written before production; the same RED run failed before imports resolved | 2 passed | Migration names its enums, checks, indexes, function, and trigger |
| 1.3 | N/A: no behavior added | Ruff E/F/I passed; focused tests passed | Downgrade drops trigger, function, indexes, table, and enums |
| 2.1-2.3 | `pytest tests/modules/audit/test_service.py tests/modules/audit/test_router.py` failed at collection before audit read modules existed. | 3 passed including PostgreSQL/HTTPX harness | Centralized mapping/order; Spanish 422 rejects incompatible action/resource and time ranges without reads |
| 3.1 | `pytest tests/integration/test_payments_postgres.py -k audit` failed: expected audit events were absent. | 1 passed PostgreSQL/HTTPX harness | Covers create/replay/process/rejection/cancel/provider exception outcomes. |
| 3.2 | Payment unit tests failed before `payment_audit_details` existed. | 11 passed | Stages domain success and provider result events at their commit boundary. |
| 3.3 | Existing payment/ledger approval tests passed before refactor. | 23 focused tests passed | Keeps the durable PROCESSING claim and ledger rollback behavior. |
| 4.1 | `pytest tests/modules/reconciliation/test_service.py -k audit` failed: audit events were absent. | 2 passed | Triangulates ingest/replay/conflict and reconciliation result/replay/conflict. |
| 4.2 | The RED audit assertions preceded reconciliation service changes. | 17 focused unit/PostgreSQL tests passed | Success events stage before their domain commit; known failures rollback then commit a separate event. |
| 4.3 | Existing race and owner-isolation tests formed the safety net. | 17 passed; Ruff/import/diff checks passed | Retains savepoint recovery, Decimal/enum equality, and unchanged routes. |
| 5.1 | Full suite initially failed collection with three `import file mismatch` errors because audit and payments had same-basename test modules without package markers. | Added empty `tests/modules/audit/__init__.py` and `tests/modules/payments/__init__.py`; full suite passed: 188 passed in 44.69s. Migration harness passed: 1 passed in 9.68s. | Markers restore the existing test-package convention only; no production behavior changed. |
| 5.2 | N/A: verification-only task; no audit behavior was added. | Excluded-flow focused suite passed: 17 passed, 21 deselected in 1.95s; Ruff E/F/I, application import, and diff check passed. | Static call-site inventory confines audit staging to payment and reconciliation services; audit router exposes GET routes only. |
## Work Unit Evidence
| Evidence | Result |
|---|---|
| Focused test command | `./.venv/Scripts/python.exe -m pytest tests/modules/audit/test_model.py tests/alembic/test_audit_migration.py` — 2 passed in 6.03s |
| Runtime harness | Disposable PostgreSQL: `upgrade head` → `downgrade f4c4e8a1d5f3` → `upgrade head`; persisted event rejects both UPDATE and DELETE with `DBAPIError` — passed |
| Rollback boundary | Revert `app/modules/audit/`, `alembic/versions/a7d3c2e9f1b6_add_audit_events.py`, the Alembic metadata import, and the two audit tests. |
| Phase 2 focused tests | `pytest tests/modules/audit/test_service.py tests/modules/audit/test_router.py` — 2 passed. |
| Phase 2 runtime harness | Disposable PostgreSQL + HTTPX-backed TestClient: list/detail, filters, pagination, owner isolation, UTC, and foreign 404 — 3 passed in 6.60s. |
| Phase 2 Ruff / rollback | Ruff E/F/I passed; revert read schemas/service/router/exceptions, app registration, tests, and Phase 2 progress. |
| Phase 3 focused/runtime | `pytest tests/modules/payments/test_service.py tests/integration/test_payments_postgres.py tests/integration/test_ledger_postgres.py` - 23 passed; PostgreSQL/HTTPX audit flow passed. |
| Phase 3 Ruff / import | `ruff check app tests` and `python -c "import app.main"` passed. |
| Phase 3 rollback | Revert payment audit hooks and the Phase 3 payment/ledger tests without touching reconciliation. |
| Phase 4 focused/runtime | `pytest tests/modules/reconciliation/test_service.py tests/integration/test_reconciliation_evidence_postgres.py` — 17 passed; two PostgreSQL sessions and HTTPX covered ingest/replay/conflict, reconcile result/replay/race/rollback/isolation. |
| Phase 4 quality / rollback | `ruff check app tests --select E,F,I`, `python -c "import app.main"`, and `git diff --check` passed; revert reconciliation audit hooks and reconciliation tests only. |
| Phase 5 full verification | `./.venv/Scripts/python.exe -m pytest` — initial RED: three collection errors from duplicate un-packaged test module names; after adding the two empty package markers, 188 passed in 44.69s. |
| Phase 5 migration / trigger harness | `./.venv/Scripts/python.exe -m pytest tests/alembic/test_audit_migration.py -q` — 1 passed in 9.68s; the harness created a disposable PostgreSQL database, ran `upgrade head` -> `downgrade f4c4e8a1d5f3` -> `upgrade head`, then rejected both `UPDATE` and `DELETE` of `audit_events` with `DBAPIError`. |
| Phase 5 quality | `./.venv/Scripts/python.exe -c "import app.main"`; `./.venv/Scripts/ruff.exe check app tests --select E,F,I`; and `git diff --check` — all passed. |
| Phase 5 excluded flows | `pytest tests/modules/auth/test_router.py tests/modules/auth/test_dependencies.py tests/modules/payments/test_router.py tests/modules/payments/test_service.py -k "register or login or missing or invalid or create_maps_conflict or provider_interruption" -q` — 17 passed, 21 deselected in 1.95s. This covers GET/read-only audit routing in the full suite, registration/login, malformed payload/generic 422 rejection, missing/invalid JWT, and provider interruption; the staging-call inventory is limited to payment and reconciliation services. |
| Phase 5 rollback / evidence preservation | Revert only `tests/modules/audit/__init__.py`, `tests/modules/payments/__init__.py`, and Phase 5 artifact entries to undo this verification fix. The functional audit rollback boundary remains the audited module/integration commits plus migration downgrade; preserve or export production audit evidence before any downgrade because it drops the immutable audit table. |
## Remaining Tasks
- None — all 14 tasks are complete.
