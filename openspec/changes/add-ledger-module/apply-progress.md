# Apply Progress: Add Ledger Module

## Completed Tasks

- [x] 1.1 RED: immutable Ledger model and PostgreSQL migration tests
- [x] 1.2 GREEN: Ledger enums/models, Alembic metadata wiring, and reversible migration
- [x] 1.3 REFACTOR/evidence: focused automated checks and manual migration harness
- [x] 2.1 RED: provider snapshot, journal service, and PostgreSQL finalization tests
- [x] 2.2 GREEN: atomic payment finalization with Ledger posting hook
- [x] 2.3 REFACTOR/evidence: focused automated checks and PostgreSQL runtime harness

## Pending Tasks

- [ ] 3.1-3.3 Read-only Ledger API
- [ ] 4.1-4.2 Closure

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `tests/modules/ledger/test_model.py`, `tests/alembic/test_ledger_migration.py` | Unit + PostgreSQL migration integration | N/A (new Ledger test files) | `./.venv/Scripts/python.exe -m pytest tests/modules/ledger/test_model.py tests/alembic/test_ledger_migration.py` exited 1 before production code: `ModuleNotFoundError: app.modules.ledger.enums` | Same command exited 0: 4 passed | Two model-contract cases plus real PostgreSQL partial/unbalanced rejection and balanced-postings acceptance; the disposable database ran `upgrade head -> downgrade base -> upgrade head` | Ruff reformatted seven touched files; focused tests remained 4 passed |
| 1.2 | Same files | Unit + PostgreSQL migration integration | `./.venv/Scripts/python.exe -m pytest tests/alembic/test_payments_migration.py` exited 0: 2 passed before modifying `alembic/env.py` | Covered by 1.1 RED | Focused command exited 0: 4 passed | Same model and PostgreSQL cases exercise the metadata and migration contract | Kept model helpers local and migration trigger validation deferred; Ruff and focused tests passed |
| 1.3 | Same files | Evidence + manual PostgreSQL migration harness | 4/4 focused tests passing before evidence close | Existing RED scenarios preserved | Focused suite remained 4 passed | Deferred partial/unbalanced rejection and balanced-postings acceptance remained covered | User reported success for `upgrade head -> current -> downgrade c4d8e9f0a1b2 -> upgrade head`; independent verification confirmed `e8a1d5f3c9b4 (head)` with PostgreSQL transactional DDL |
| 2.1 | `tests/modules/payments/test_provider.py`, `tests/modules/payments/test_service.py`, `tests/modules/ledger/test_service.py`, `tests/integration/test_ledger_postgres.py` | Unit + PostgreSQL integration | `./.venv/Scripts/python.exe -m pytest tests/modules/payments/test_provider.py tests/modules/payments/test_service.py tests/integration/test_payments_postgres.py` exited 0: 17 passed before production changes | Focused new-test command exited 1 before production code: missing `PaymentProviderInput` and `app.modules.ledger.service` | Focused command exited 0: 10 passed after initial implementation | Added rejected/failed branches, provider transaction inspection, local posting failure rollback, and two-session convergence | Ruff import normalization and focused suite remained passing |
| 2.2 | Same files | Unit + PostgreSQL integration | 17/17 regression safety net | Covered by 2.1 RED | `./.venv/Scripts/python.exe -m pytest tests/modules/payments/test_service.py tests/integration/test_payments_postgres.py` exited 0: 14 passed after adapting the existing provider-boundary assertion | Success, non-success, rollback, and contention execute against real PostgreSQL | Kept Ledger flush-only and Payment service as the sole commit/rollback owner |
| 2.3 | Same files | Evidence + PostgreSQL runtime harness | 24/24 focused and payment regression tests passed before final retry test | Completed-retry transaction-close assertion exited 1 before finalization cleanup | `./.venv/Scripts/python.exe -m pytest tests/modules/payments/test_provider.py tests/modules/payments/test_service.py tests/modules/ledger/test_service.py tests/integration/test_payments_postgres.py tests/integration/test_ledger_postgres.py` exited 0: 25 passed | PostgreSQL runtime suite covers frozen input, balanced postings, non-success absence, rollback to `processing`, convergence, and retry reuse | Ruff/import/diff checks passed; user manual end-to-end sandbox verification remains pending for Phase 4 |

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

## Workload / PR Boundary

- Delivery mode: auto-chain / stacked-to-main.
- Current slice: PR 2 — atomic payment finalization only, stacked onto PR 1 and intended to target `main` after its predecessor merges.
- Included: frozen provider input, lock/reload finalization, flush-only Ledger creation, and unit/PostgreSQL tests.
- Excluded: read-only Ledger schema/router/application registration, final closure checks, and user manual end-to-end verification.

## Deviations and Issues

- No design deviation. Deferred aggregate integrity is implemented with PostgreSQL constraint triggers because a row `CHECK` cannot inspect sibling postings.
- Manual migration verification is recorded as complete; no production or test files changed during this evidence update.
- No Phase 2 design deviation. The user explicitly postponed manual end-to-end testing until the complete Ledger module is implemented; Phase 2 closes only on automated PostgreSQL runtime evidence.
