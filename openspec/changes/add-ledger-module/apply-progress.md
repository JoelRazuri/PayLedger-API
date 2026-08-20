# Apply Progress: Add Ledger Module

## Completed Tasks

- [x] 1.1 RED: immutable Ledger model and PostgreSQL migration tests
- [x] 1.2 GREEN: Ledger enums/models, Alembic metadata wiring, and reversible migration
- [x] 1.3 REFACTOR/evidence: focused automated checks and manual migration harness

## Pending Tasks

- [ ] 2.1-2.3 Atomic payment finalization
- [ ] 3.1-3.3 Read-only Ledger API
- [ ] 4.1-4.2 Closure

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `tests/modules/ledger/test_model.py`, `tests/alembic/test_ledger_migration.py` | Unit + PostgreSQL migration integration | N/A (new Ledger test files) | `./.venv/Scripts/python.exe -m pytest tests/modules/ledger/test_model.py tests/alembic/test_ledger_migration.py` exited 1 before production code: `ModuleNotFoundError: app.modules.ledger.enums` | Same command exited 0: 4 passed | Two model-contract cases plus real PostgreSQL partial/unbalanced rejection and balanced-postings acceptance; the disposable database ran `upgrade head -> downgrade base -> upgrade head` | Ruff reformatted seven touched files; focused tests remained 4 passed |
| 1.2 | Same files | Unit + PostgreSQL migration integration | `./.venv/Scripts/python.exe -m pytest tests/alembic/test_payments_migration.py` exited 0: 2 passed before modifying `alembic/env.py` | Covered by 1.1 RED | Focused command exited 0: 4 passed | Same model and PostgreSQL cases exercise the metadata and migration contract | Kept model helpers local and migration trigger validation deferred; Ruff and focused tests passed |
| 1.3 | Same files | Evidence + manual PostgreSQL migration harness | 4/4 focused tests passing before evidence close | Existing RED scenarios preserved | Focused suite remained 4 passed | Deferred partial/unbalanced rejection and balanced-postings acceptance remained covered | User reported success for `upgrade head -> current -> downgrade c4d8e9f0a1b2 -> upgrade head`; independent verification confirmed `e8a1d5f3c9b4 (head)` with PostgreSQL transactional DDL |

## Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused test command | `./.venv/Scripts/python.exe -m pytest tests/modules/ledger/test_model.py tests/alembic/test_ledger_migration.py` — exit 0, 4 passed |
| Lint command | `./.venv/Scripts/python.exe -m ruff check app/modules/ledger alembic/env.py alembic/versions/e8a1d5f3c9b4_create_ledger_tables.py tests/modules/ledger/test_model.py tests/alembic/test_ledger_migration.py` — exit 0, all checks passed |
| Runtime harness | Disposable PostgreSQL database: Alembic `upgrade head -> downgrade base -> upgrade head`; deferred trigger rejected both a one-posting journal and unequal debit/credit postings at transaction commit; generated database was terminated and dropped |
| Manual migration harness | User reported success for `./.venv/Scripts/alembic.exe upgrade head`, `./.venv/Scripts/alembic.exe current`, `./.venv/Scripts/alembic.exe downgrade c4d8e9f0a1b2`, then `./.venv/Scripts/alembic.exe upgrade head`; independent verification confirmed `e8a1d5f3c9b4 (head)` with PostgreSQL transactional DDL |
| Rollback boundary | Revert `app/modules/ledger/`, `alembic/versions/e8a1d5f3c9b4_create_ledger_tables.py`, the Ledger metadata import in `alembic/env.py`, and the two Ledger test files; then downgrade revision `e8a1d5f3c9b4` |

## Workload / PR Boundary

- Delivery mode: auto-chain / stacked-to-main.
- Current slice: PR 1 — immutable persistence only, intended to target `main` after predecessor state.
- Included: Ledger enums/models, migration/metadata wiring, and their tests.
- Excluded: payment finalization, providers, services, router/application registration, and all later SDD tasks.

## Deviations and Issues

- No design deviation. Deferred aggregate integrity is implemented with PostgreSQL constraint triggers because a row `CHECK` cannot inspect sibling postings.
- Manual migration verification is recorded as complete; no production or test files changed during this evidence update.
