# Apply Progress: Add Authentication

## Delivery Context

- Delivery strategy: `auto-chain`
- Chain strategy: `stacked-to-main`
- Current work unit: Unit 2, auth workflows
- Completed boundaries: PR/commit 1 foundation and PR/commit 2 workflows
- Current boundary: users persistence primitives through authenticated-user
  dependency; HTTP integration remains pending
- Strict TDD: enabled

## Completed Tasks

- [x] 1.1 Schema RED coverage
- [x] 1.2 Security RED coverage
- [x] 1.3 Model and migration RED coverage
- [x] 2.1 Dependencies and JWT settings
- [x] 2.2 User credential model and reversible migration
- [x] 2.3 Reusable user input and auth schemas
- [x] 2.4 Argon2 and JWT security helpers
- [x] 3.1 Users-service RED coverage
- [x] 3.2 Normalized credential persistence primitives
- [x] 3.3 Auth-service RED coverage
- [x] 3.4 Registration, login, and identity-resolution services
- [x] 3.5 Bearer dependency RED-GREEN coverage

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
| 3.1 | `tests/modules/users/test_service.py` | Unit | 34/34 baseline | Focused collection failed because credential creation primitive did not exist | Paired task 3.2 passed | Mixed-case lookup, successful persistence, existing duplicate, and integrity race | Query/persistence boundary remains inside users; 18/18 passed |
| 3.2 | Users service tests above | Unit | 34/34 baseline | Covered by task 3.1 RED | Normalized lookup and hash-only creation passed | Pre-query duplicate and commit-race rollback exercise separate paths | Existing public creation remains untouched until unit 3; 18/18 passed |
| 3.3 | `tests/modules/auth/test_service.py` | Unit | 34/34 baseline | Focused collection failed because auth exceptions/service did not exist | Paired task 3.4 passed | Register/duplicate, active/wrong/unknown/inactive login, active/unknown/inactive identity | External functions patched at service boundary; 18/18 passed |
| 3.4 | Auth service tests above | Unit | 34/34 baseline | Covered by task 3.3 RED | Registration, token login, and identity resolution passed | Unknown email performs dummy verification; inactive status is checked only after valid password | One-way `auth -> users` dependency preserved; 18/18 passed |
| 3.5 | `tests/modules/auth/test_dependencies.py` | Unit/integration | 34/34 baseline | Focused collection failed because bearer dependency did not exist | Missing, invalid, valid, unknown, and inactive cases passed | Missing, malformed, expired, unknown, inactive, and successful identity paths | Shared credential exception helper and `Never` return clarify fail-closed flow; 19/19 passed |

## Test Summary

- Baseline: `13 passed in 0.85s`
- Initial RED: two collection errors for missing auth modules
- Settings RED: `1 failed, 1 passed`
- Focused GREEN: `21 passed in 1.06s`
- Focused post-refactor: `21 passed in 1.34s`
- Full compatibility suite: `34 passed in 2.41s`
- Unit 2 initial RED: three collection errors for missing workflow APIs
- Unit 2 focused GREEN: `18 passed in 0.99s`
- Unit 2 focused post-refactor: `19 passed in 1.41s`
- Unit 2 full compatibility suite: `53 passed in 2.54s`
- Layers used: unit and migration integration
- Approval tests: none; existing name behavior was preserved through its current tests
- Pure/bounded helpers created: password hash/verify, dummy verify, JWT encode/decode

## Work Unit 1 Evidence

| Evidence | Result |
|---|---|
| Focused test | `.\.venv\Scripts\python.exe -m pytest tests/core/test_settings.py tests/modules/auth/test_schema.py tests/modules/auth/test_security.py tests/modules/users/test_model.py tests/alembic/test_user_credentials_migration.py -q` -> 21 passed |
| Runtime harness | With process-local `JWT_SECRET`: Alembic current `3e81fa4d59d2`; upgrade to `b73c6cb6e54a`; downgrade to `3e81fa4d59d2`; upgrade to `b73c6cb6e54a`; final current `b73c6cb6e54a (head)` on local PostgreSQL |
| Static quality | `ruff check app tests alembic` -> All checks passed |
| Import | With process-local `JWT_SECRET`: `import app.main` -> OK |
| Rollback boundary | Revert `requirements.txt`, JWT fields in `app/core/settings.py`, auth schema/security package, user model/schema credential changes, tests/package markers, and migration `b73c6cb6e54a`; run `alembic downgrade 3e81fa4d59d2`. Workflow/router files are untouched. |

## Work Unit 2 Evidence

| Evidence | Result |
|---|---|
| Focused test | `.\.venv\Scripts\python.exe -m pytest tests/modules/auth/test_service.py tests/modules/auth/test_dependencies.py tests/modules/users/test_service.py -q` -> 19 passed |
| Runtime harness | With process-local `JWT_SECRET`, a real PostgreSQL session registered a unique mixed-case email, verified that only an Argon2 hash was stored, logged in case-insensitively, decoded/resolved the bearer identity through `get_current_user`, asserted active state, and deleted the exact harness user -> `service runtime OK: user_id=1, token_user_id=1` |
| Full suite | `.\.venv\Scripts\python.exe -m pytest -q` -> 53 passed |
| Static quality | `.\.venv\Scripts\ruff.exe check app tests alembic` -> All checks passed |
| Import | With process-local `JWT_SECRET`: `import app.main` -> OK |
| Rollback boundary | Revert credential primitives in `app/modules/users/service.py`, `app/modules/auth/{exceptions,service,dependencies}.py`, and their three focused test files. Foundation, routers, `app/main.py`, and database schema remain intact. |

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
- Unit 2 introduced no design deviation. Dependencies form the HTTP-aware
  authentication boundary and translate domain failures to Spanish 401/403;
  services remain independent of HTTP.

## Remaining Tasks

Tasks 4.1 through 5.2 remain pending for HTTP integration and final verification.
