# Apply Progress: Add Authentication

## Delivery Context

- Delivery strategy: `auto-chain`
- Chain strategy: `stacked-to-main`
- Current work unit: Unit 1, credential foundation and schema
- Intended boundary: PR/commit 1 only; workflow and HTTP integration remain pending
- Strict TDD: enabled

## Completed Tasks

- [x] 1.1 Schema RED coverage
- [x] 1.2 Security RED coverage
- [x] 1.3 Model and migration RED coverage
- [x] 2.1 Dependencies and JWT settings
- [x] 2.2 User credential model and reversible migration
- [x] 2.3 Reusable user input and auth schemas
- [x] 2.4 Argon2 and JWT security helpers

## TDD Cycle Evidence

| Task | Test file | Layer | Safety net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `tests/modules/auth/test_schema.py` | Unit | 13/13 baseline | Collection failed because auth schema did not exist | Paired task 2.3 passed | Password 8/128 and 7/129; mixed-case email; safe response | Shared `UserInput` removed validator duplication; 21/21 passed |
| 1.2 | `tests/modules/auth/test_security.py` | Unit | 13/13 baseline | Collection failed because auth security did not exist | Paired task 2.4 passed | Correct/wrong/dummy passwords; valid/invalid/expired/bad-subject JWTs | Constants and bounded helpers extracted; 21/21 passed |
| 1.3 | `tests/modules/users/test_model.py`, `tests/alembic/test_user_credentials_migration.py` | Unit/integration | 13/13 baseline | New credential fields and revision were absent | Paired task 2.2 passed | Metadata SQL plus upgrade and downgrade paths | Migration loader made path-explicit; 21/21 passed |
| 2.1 | `tests/core/test_settings.py` | Unit | 13/13 baseline | 1 failed because `jwt_secret` was rejected as extra | 2/2 settings tests passed | Required secret plus HS256/30-minute defaults | Test-only environment bootstrap centralized in `tests/conftest.py`; 21/21 passed |
| 2.2 | Model and migration tests above | Unit/integration | 13/13 baseline | Covered by task 1.3 RED | Required mappings and reversible revision passed | Application default and transient migration default exercise distinct paths | Manual migration review plus real PostgreSQL cycle passed |
| 2.3 | Schema tests above | Unit | 13/13 baseline | Covered by task 1.1 RED | Registration and safe response schemas passed | Both accepted and rejected boundaries covered | Existing `UserCreate` remains compatible until HTTP ownership moves |
| 2.4 | Security tests above | Unit | 13/13 baseline | Covered by task 1.2 RED | Real Argon2 and PyJWT tests passed | Success, mismatch, dummy, malformed, expired, and invalid subject paths covered | Focused helpers preserve a small auth API; 21/21 passed |

## Test Summary

- Baseline: `13 passed in 0.85s`
- Initial RED: two collection errors for missing auth modules
- Settings RED: `1 failed, 1 passed`
- Focused GREEN: `21 passed in 1.06s`
- Focused post-refactor: `21 passed in 1.34s`
- Full compatibility suite: `34 passed in 2.41s`
- Layers used: unit and migration integration
- Approval tests: none; existing name behavior was preserved through its current tests
- Pure/bounded helpers created: password hash/verify, dummy verify, JWT encode/decode

## Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused test | `.\.venv\Scripts\python.exe -m pytest tests/core/test_settings.py tests/modules/auth/test_schema.py tests/modules/auth/test_security.py tests/modules/users/test_model.py tests/alembic/test_user_credentials_migration.py -q` -> 21 passed |
| Runtime harness | With process-local `JWT_SECRET`: Alembic current `3e81fa4d59d2`; upgrade to `b73c6cb6e54a`; downgrade to `3e81fa4d59d2`; upgrade to `b73c6cb6e54a`; final current `b73c6cb6e54a (head)` on local PostgreSQL |
| Static quality | `ruff check app tests alembic` -> All checks passed |
| Import | With process-local `JWT_SECRET`: `import app.main` -> OK |
| Rollback boundary | Revert `requirements.txt`, JWT fields in `app/core/settings.py`, auth schema/security package, user model/schema credential changes, tests/package markers, and migration `b73c6cb6e54a`; run `alembic downgrade 3e81fa4d59d2`. Workflow/router files are untouched. |

## Migration Review

The database was confirmed empty before planning. The upgrade adds
`hashed_password VARCHAR(255) NOT NULL`, adds `is_active BOOLEAN NOT NULL` with
a transient `true` server default, and removes that default immediately. The
downgrade drops `is_active` before `hashed_password`. `alembic/env.py` already
imports the user model, so no discovery change was necessary.

## Deviations and Issues

- No design deviation.
- A full-suite pytest module-name collision was found after focused GREEN and
  resolved by adding package markers under `tests/`; the final full suite passes.
- `jwt_secret` intentionally has no production default. Tests set an explicit
  test-only value, and non-test commands must receive `JWT_SECRET` through the
  environment or local `.env`.

## Remaining Tasks

Tasks 3.1 through 5.2 remain pending for the workflow and HTTP slices.
