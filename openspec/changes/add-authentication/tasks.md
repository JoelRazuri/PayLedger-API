# Tasks: Add Authentication

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 900-1,300 |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR 1 foundation -> PR 2 workflows -> PR 3 HTTP integration |
| Delivery strategy | auto-chain |
| Chain strategy | stacked-to-main |

Decision needed before apply: No
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Credential foundation and schema | PR 1 | `.\.venv\Scripts\python.exe -m pytest tests/modules/auth/test_schema.py tests/modules/auth/test_security.py tests/modules/users/test_model.py tests/alembic/test_user_credentials_migration.py` | `alembic upgrade head; alembic downgrade -1; alembic upgrade head` on local PostgreSQL | Dependencies, settings, model, migration, schemas, security |
| 2 | Auth workflows | PR 2 | `.\.venv\Scripts\python.exe -m pytest tests/modules/auth/test_service.py tests/modules/auth/test_dependencies.py tests/modules/users/test_service.py` | Service register/login/token scenario | Users primitives and auth workflow/dependency files |
| 3 | API integration and route ownership | PR 3 | `.\.venv\Scripts\python.exe -m pytest tests/modules/auth/test_router.py tests/modules/users/test_router.py` | `uvicorn app.main:app`; Swagger register, login, authorize, `/auth/me`, public reads | Router/wiring and `POST /users` removal |

## Phase 1: Foundation RED

- [x] 1.1 Add failing `tests/modules/auth/test_schema.py` coverage for password boundaries, normalized email, shared name rules, and safe responses.
- [x] 1.2 Add failing `tests/modules/auth/test_security.py` coverage for Argon2 verification and JWT subject, expiry, safety, and decode failures.
- [x] 1.3 Add failing model/migration tests for non-null hash, active default, metadata, upgrade, and downgrade.

## Phase 2: Foundation GREEN

- [x] 2.1 Pin auth dependencies; configure required `jwt_secret`, HS256, and 30-minute lifetime in `app/core/settings.py` and tests.
- [x] 2.2 Add credential/state mappings to `app/modules/users/model.py`; create the reversible migration and preserve `alembic/env.py` model discovery.
- [x] 2.3 Extract reusable name input in `users/schema.py`; add auth register, token, and safe response schemas.
- [x] 2.4 Create `app/modules/auth/security.py` implementing Argon2 hashing/verification, fixed dummy verification, and bounded JWT encode/decode helpers.

## Phase 3: Workflow RED-GREEN

- [x] 3.1 Add failing `tests/modules/users/test_service.py` cases for normalized lookup, credential creation, and duplicate rollback.
- [x] 3.2 Implement normalized lookup/create primitives in `app/modules/users/service.py`.
- [x] 3.3 Add failing auth-service tests for registration, duplicates, active login, wrong/unknown credentials with dummy verification, and inactive rejection.
- [x] 3.4 Create `app/modules/auth/exceptions.py` and `app/modules/auth/service.py` to register, authenticate, and resolve users through users primitives.
- [x] 3.5 Add failing dependency tests for missing/invalid/expired tokens and valid, unknown, or inactive users; implement `app/modules/auth/dependencies.py`.

## Phase 4: HTTP Integration RED-GREEN

- [x] 4.1 Move registration/name tests into failing `tests/modules/auth/test_router.py`; cover safe 201, duplicate 409, login 200/401/403, `/auth/me`, and Spanish errors.
- [x] 4.2 Add failing assertions for public GET routes and unavailable `POST /users`.
- [x] 4.3 Create `app/modules/auth/router.py`, remove user creation from `app/modules/users/router.py`, and include the auth router in `app/main.py`.

## Phase 5: Refactor and Verification

- [x] 5.1 Refactor duplication while preserving `auth -> users`; run each focused suite.
- [x] 5.2 Run full pytest, Ruff, application import, and the local Alembic upgrade/downgrade/upgrade harness; record results for SDD verification.
