# Apply Progress: Add Ledger Module

## Completed Tasks

- [x] 1.1 RED: immutable Ledger model and PostgreSQL migration tests
- [x] 1.2 GREEN: Ledger enums/models, Alembic metadata wiring, and reversible migration
- [x] 1.3 REFACTOR/evidence: focused automated checks and manual migration harness
- [x] 2.1 RED: provider snapshot, journal service, and PostgreSQL finalization tests
- [x] 2.2 GREEN: atomic payment finalization with Ledger posting hook
- [x] 2.3 REFACTOR/evidence: focused automated checks and PostgreSQL runtime harness
- [x] 3.1 RED: Ledger schema and read-only router threat tests
- [x] 3.2 GREEN: owner-scoped journal queries, schemas, router, and application registration
- [x] 3.3 REFACTOR/evidence: automated API/runtime evidence; manual end-to-end remains Phase 4
- [x] 4.1 Closure evidence: full automated verification and user manual Swagger/end-to-end Ledger verification

## Apply Status

- All implementation and apply/verification-precondition tasks are complete.
- Next lifecycle action: run SDD Verify. After successful SDD Verify, perform post-verification workflow step 4.2 to archive the change.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `tests/modules/ledger/test_model.py`, `tests/alembic/test_ledger_migration.py` | Unit + PostgreSQL migration integration | N/A (new Ledger test files) | `./.venv/Scripts/python.exe -m pytest tests/modules/ledger/test_model.py tests/alembic/test_ledger_migration.py` exited 1 before production code: `ModuleNotFoundError: app.modules.ledger.enums` | Same command exited 0: 4 passed | Two model-contract cases plus real PostgreSQL partial/unbalanced rejection and balanced-postings acceptance; the disposable database ran `upgrade head -> downgrade base -> upgrade head` | Ruff reformatted seven touched files; focused tests remained 4 passed |
| 1.2 | Same files | Unit + PostgreSQL migration integration | `./.venv/Scripts/python.exe -m pytest tests/alembic/test_payments_migration.py` exited 0: 2 passed before modifying `alembic/env.py` | Covered by 1.1 RED | Focused command exited 0: 4 passed | Same model and PostgreSQL cases exercise the metadata and migration contract | Kept model helpers local and migration trigger validation deferred; Ruff and focused tests passed |
| 1.3 | Same files | Evidence + manual PostgreSQL migration harness | 4/4 focused tests passing before evidence close | Existing RED scenarios preserved | Focused suite remained 4 passed | Deferred partial/unbalanced rejection and balanced-postings acceptance remained covered | User reported success for `upgrade head -> current -> downgrade c4d8e9f0a1b2 -> upgrade head`; independent verification confirmed `e8a1d5f3c9b4 (head)` with PostgreSQL transactional DDL |
| 2.1 | `tests/modules/payments/test_provider.py`, `tests/modules/payments/test_service.py`, `tests/modules/ledger/test_service.py`, `tests/integration/test_ledger_postgres.py` | Unit + PostgreSQL integration | `./.venv/Scripts/python.exe -m pytest tests/modules/payments/test_provider.py tests/modules/payments/test_service.py tests/integration/test_payments_postgres.py` exited 0: 17 passed before production changes | Focused new-test command exited 1 before production code: missing `PaymentProviderInput` and `app.modules.ledger.service` | Focused command exited 0: 10 passed after initial implementation | Added rejected/failed branches, provider transaction inspection, local posting failure rollback, and two-session convergence | Ruff import normalization and focused suite remained passing |
| 2.2 | Same files | Unit + PostgreSQL integration | 17/17 regression safety net | Covered by 2.1 RED | `./.venv/Scripts/python.exe -m pytest tests/modules/payments/test_service.py tests/integration/test_payments_postgres.py` exited 0: 14 passed after adapting the existing provider-boundary assertion | Success, non-success, rollback, and contention execute against real PostgreSQL | Kept Ledger flush-only and Payment service as the sole commit/rollback owner |
| 2.3 | Same files | Evidence + PostgreSQL runtime harness | 24/24 focused and payment regression tests passed before final retry test | Completed-retry transaction-close assertion exited 1 before finalization cleanup | `./.venv/Scripts/python.exe -m pytest tests/modules/payments/test_provider.py tests/modules/payments/test_service.py tests/modules/ledger/test_service.py tests/integration/test_payments_postgres.py tests/integration/test_ledger_postgres.py` exited 0: 25 passed | PostgreSQL runtime suite covers frozen input, balanced postings, non-success absence, rollback to `processing`, convergence, and retry reuse | Ruff/import/diff checks passed; user manual end-to-end sandbox verification remains pending for Phase 4 |
| 3.1 | `tests/modules/ledger/test_schema.py`, `tests/modules/ledger/test_router.py`, `tests/modules/ledger/test_service.py` | Schema + TestClient router + query service | `./.venv/Scripts/python.exe -m pytest tests/modules/auth/test_router.py tests/modules/payments/test_router.py tests/modules/ledger/test_service.py` exited 0: 22 passed before API changes | `./.venv/Scripts/python.exe -m pytest tests/modules/ledger/test_schema.py tests/modules/ledger/test_router.py` exited 1 before production code: missing `app.modules.ledger.schema` and `router` | Schema/router suite exited 0 after production code; every GET, 401, 404, 422, and 405 threat case executes through TestClient | Added owner join/EXISTS/distinct/order query assertions and every route's missing/invalid-token matrix | Kept validation behavior local to the Ledger router and normalized imports/line lengths with Ruff |
| 3.2 | Same files | Query service + TestClient router | 22/22 auth/payment/ledger-service regression safety net | Covered by 3.1 RED | `./.venv/Scripts/python.exe -m pytest tests/modules/ledger/test_schema.py tests/modules/ledger/test_router.py tests/modules/ledger/test_service.py` exited 0: 22 passed | Filters, nested entries, all read routes, owner-safe 404, and stable query expression are covered | Kept account filtering as correlated `EXISTS` so pagination remains journal-distinct |
| 3.3 | Same files | Automated API/runtime evidence | 22/22 Unit 3 tests passing before final checks | Existing threat scenarios preserved | Combined command exited 0: 54 passed; Ruff and import checks passed | Runtime TestClient harness asserted actual app registration produces 401 for an unauthenticated read and 405 for a mutation | No code refactor beyond import/line normalization; manual Swagger/end-to-end verification is explicitly deferred to Phase 4 |

## Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused test command | `./.venv/Scripts/python.exe -m pytest tests/modules/ledger/test_model.py tests/alembic/test_ledger_migration.py` — exit 0, 4 passed |
| Lint command | `./.venv/Scripts/python.exe -m ruff check app/modules/ledger alembic/env.py alembic/versions/e8a1d5f3c9b4_create_ledger_tables.py tests/modules/ledger/test_model.py tests/alembic/test_ledger_migration.py` — exit 0, all checks passed |
| Runtime harness | Disposable PostgreSQL database: Alembic `upgrade head -> downgrade base -> upgrade head`; deferred trigger rejected both a one-posting journal and unequal debit/credit postings at transaction commit; generated database was terminated and dropped |
| Manual migration harness | User reported success for `./.venv/Scripts/alembic.exe upgrade head`, `./.venv/Scripts/alembic.exe current`, `./.venv/Scripts/alembic.exe downgrade c4d8e9f0a1b2`, then `./.venv/Scripts/alembic.exe upgrade head`; independent verification confirmed `e8a1d5f3c9b4 (head)` with PostgreSQL transactional DDL |
| Rollback boundary | Revert `app/modules/ledger/`, `alembic/versions/e8a1d5f3c9b4_create_ledger_tables.py`, the Ledger metadata import in `alembic/env.py`, and the two Ledger test files; then downgrade revision `e8a1d5f3c9b4` |

### Unit 2: Atomic payment finalization

| Evidence | Result |
|---|---|
| Focused test command | `./.venv/Scripts/python.exe -m pytest tests/modules/payments/test_provider.py tests/modules/payments/test_service.py tests/modules/ledger/test_service.py tests/integration/test_ledger_postgres.py` — exit 0, 21 passed |
| Relevant regression command | `./.venv/Scripts/python.exe -m pytest tests/modules/payments/test_service.py tests/integration/test_payments_postgres.py` — exit 0, 14 passed |
| Final automated evidence | `./.venv/Scripts/python.exe -m pytest tests/modules/payments/test_provider.py tests/modules/payments/test_service.py tests/modules/ledger/test_service.py tests/integration/test_payments_postgres.py tests/integration/test_ledger_postgres.py` — exit 0, 25 passed |
| Lint/import commands | Ruff check on all Unit 2 production/test files exited 0 with all checks passed; `./.venv/Scripts/python.exe -c "import app.main"` exited 0 |
| Runtime harness | Disposable PostgreSQL database via Alembic `upgrade head`; six integration scenarios prove provider I/O sees a frozen scalar input with no Session transaction, one balanced two-posting journal on success, no journal on rejected/failed outcomes, rollback to `processing` after local posting failure, two-session convergence to one journal, and retry reuse without an open lock transaction. |
| Manual end-to-end verification | Pending by explicit workflow decision: run one user manual sandbox/Swagger verification for the complete Ledger module in Phase 4 before closure/archive. No manual success is claimed for Unit 2. |
| Rollback boundary | Revert `app/modules/payments/provider.py`, `app/modules/payments/service.py`, `app/modules/ledger/exceptions.py`, `app/modules/ledger/service.py`, and the four Unit 2 test files; this removes only frozen provider input and atomic finalization journaling. |

### Unit 3: Authenticated journal discovery

| Evidence | Result |
|---|---|
| Focused test command | `./.venv/Scripts/python.exe -m pytest tests/modules/ledger/test_schema.py tests/modules/ledger/test_router.py tests/modules/ledger/test_service.py` — exit 0, 22 passed |
| Relevant regression command | `./.venv/Scripts/python.exe -m pytest tests/modules/auth/test_router.py tests/modules/payments/test_router.py tests/modules/payments/test_service.py` — exit 0, 32 passed; combined Unit 3/regression command — exit 0, 54 passed |
| Lint/import commands | `./.venv/Scripts/python.exe -m ruff check app/main.py app/modules/ledger tests/modules/ledger/test_schema.py tests/modules/ledger/test_router.py tests/modules/ledger/test_service.py` — exit 0, all checks passed; `./.venv/Scripts/python.exe -c "import app.main"` — exit 0 |
| Runtime harness | `./.venv/Scripts/python.exe -c "from fastapi.testclient import TestClient; from app.main import app; ..."` — exit 0; registered app returned 401 for `GET /ledger/journals` without JWT and 405 for `POST /ledger/journals` |
| Manual end-to-end verification | Pending by explicit workflow decision: the user performs one complete sandbox/Swagger verification for the completed Ledger module in Phase 4. No manual success is claimed for Unit 3. |
| Rollback boundary | Revert `app/modules/ledger/schema.py`, `app/modules/ledger/router.py`, the read-query additions in `app/modules/ledger/service.py`, `LedgerNotFoundError`, the Ledger router import/registration in `app/main.py`, and the three Unit 3 test files; this removes only the read-only API slice. |

## Phase 4.1 Closure Evidence

| Evidence | Result |
|---|---|
| Full test suite | `./.venv/Scripts/python.exe -m pytest` — exit 0, 132 passed |
| Full lint | `./.venv/Scripts/python.exe -m ruff check app tests` — exit 0, all checks passed |
| Import check | `./.venv/Scripts/python.exe -c "import app.main"` — exit 0, `app.main import passed` |
| Disposable migration cycle | `./.venv/Scripts/python.exe -m pytest tests/alembic/test_ledger_migration.py` — exit 0, 2 passed; created and dropped a generated PostgreSQL database after `upgrade head -> downgrade base -> upgrade head`, including deferred-balance checks |
| Automated TestClient smoke | Fresh disposable PostgreSQL database and `alembic upgrade head`; registered a user, logged in, created and processed an ARS payment with the sandbox provider, then read its completed Ledger journal — exit 0. The database was terminated and dropped in `finally`. |
| Harness setup note | The initial smoke fixture used the reserved `.test` email domain and correctly received registration `422` from email validation. The fixture was changed to `example.com`; this was harness-only and no candidate source changed. |
| User manual Swagger/end-to-end verification | **Passed, user-reported.** The complete Swagger/end-to-end plan worked: a completed payment generated a balanced journal; owner isolation, filters/pagination, and read-only behavior all worked. |

## Workload / PR Boundary

- Delivery mode: auto-chain / stacked-to-main.
- Current slice: PR 3 — authenticated read-only API, stacked after the persistence and payment-finalization slices and intended to target `main` after its predecessor merges.
- Included: journal schemas, owner-scoped query service, read-only router/application registration, and Unit 3 automated tests.
- Excluded: final closure checks, migration cycle, archive, and user manual end-to-end verification.

## Deviations and Issues

- No design deviation. Deferred aggregate integrity is implemented with PostgreSQL constraint triggers because a row `CHECK` cannot inspect sibling postings.
- Manual migration verification is recorded as complete; no production or test files changed during this evidence update.
- No Phase 2 design deviation. The user explicitly postponed manual end-to-end testing until the complete Ledger module is implemented; Phase 2 closes only on automated PostgreSQL runtime evidence.
- No Phase 3 design deviation. The explicit workflow defers manual Swagger/end-to-end verification to the single final Phase 4 gate, so Phase 3 closes only on automated API/runtime evidence.
- Phase 4.1 is complete: automated evidence passed and the user reported that the complete Swagger/end-to-end Ledger plan worked. Archive step 4.2 is a post-verification lifecycle action and remains unperformed until SDD Verify succeeds.

## Focused Remediation Evidence (V-001, V-002)

- Scope: added runtime proof for the two verification blockers only. The existing `verify-report.md` remains an authoritative **FAIL** until SDD Verify is rerun; this evidence does not claim a replacement verdict.
- Production correction: PostgreSQL retrieved `TIMESTAMPTZ` values in the session timezone (`America/Buenos_Aires`). Ledger retrieval services now normalize `occurred_at` and `created_at` to UTC before API exposure, preserving their instants.

### Strict TDD Evidence

- Safety net: `./.venv/Scripts/python.exe -m pytest tests/integration/test_ledger_postgres.py` â€” exit 0, 6 passed before edits.
- RED: wrote both integration tests before production edits. V-001 was already green (coverage-only); V-002 exited 1 (7 passed, 1 failed) because retrieved `created_at.tzinfo` was `America/Buenos_Aires`, not `UTC`.
- GREEN/refactor: normalized Ledger retrieval timestamps to UTC, then focused tests passed 8/8 and Ruff passed after formatting.

### Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused/runtime | `./.venv/Scripts/python.exe -m pytest tests/integration/test_ledger_postgres.py` â€” exit 0, 8 passed; real disposable PostgreSQL proves cancellation has no journal and a fresh retrieval preserves the processed-time instant with UTC timestamps. |
| Full/lint/import | Pytest: exit 0, 134 passed. Ruff `check app tests`: exit 0. `import app.main`: exit 0. |
| Rollback | Revert `tests/integration/test_ledger_postgres.py` and `app/modules/ledger/service.py`; only blocker coverage and Ledger API UTC normalization are removed. |
