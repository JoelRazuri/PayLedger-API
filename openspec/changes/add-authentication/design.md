# Design: Add Authentication

## Technical Approach

Add an `auth` feature that owns registration, credential verification, JWTs,
and current-user resolution while depending one-way on `users` persistence.
`users` keeps the entity and public reads; its public creation route is removed.
Pydantic validates inputs, services remain HTTP-independent, and routers map
domain exceptions to Spanish responses.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Module boundary | `auth -> users`; auth hashes and orchestrates, users queries/persists | Keep creation in users; full auth framework | Preserves feature ownership without circular dependencies or hidden framework behavior |
| Shared name rules | Extract a reusable input base/mixin in `users/schema.py`; `RegisterRequest` extends it | Import auth schema into users; duplicate validator | Keeps entity validation reusable while preserving dependency direction |
| Password/JWT | `pwdlib[argon2]`, PyJWT HS256, `sub=str(user.id)`, UTC `exp` at 30 minutes | Reversible encryption; email subject | Argon2 is one-way and user ID is immutable |
| Configuration | Required `jwt_secret`; `jwt_algorithm="HS256"` and `access_token_expire_minutes=30` in `Settings` | Committed/default secret | Missing secrets fail startup instead of silently enabling forgeable tokens |
| Persistence | Users service exposes normalized lookup and credential-bearing create primitives; auth passes only the hash | Auth writes SQLAlchemy directly | Retains existing service boundary and transaction handling |
| Login privacy | Normalize email, verify a fixed dummy Argon2 hash for unknown users, then return the same 401 as wrong passwords | Skip verification for unknown email | Reduces account-enumeration timing differences; inactive status is revealed only after valid credentials |
| Tests | Mock service/session boundaries for most tests; selectively use real Argon2 and PyJWT | Require PostgreSQL for every test | Fast deterministic coverage without weakening security-library integration evidence |

## Data Flow

```text
register -> auth router -> validate/normalize -> hash -> users service -> users table
login    -> OAuth2 form -> lookup -> verify -> active check -> sign JWT
/me      -> bearer token -> decode sub -> users lookup -> active check -> safe profile
```

## File Changes

| File | Action | Description |
|---|---|---|
| `app/modules/auth/{schema,security,service,dependencies,router,exceptions}.py` | Create | Auth contracts, crypto, workflows, bearer dependency, routes, domain errors |
| `app/modules/users/{model,schema,service,router}.py` | Modify | Add credential/state fields, reusable name input, normalized persistence, remove POST |
| `app/core/settings.py`, `app/main.py` | Modify | Required JWT secret/config and auth router registration |
| `alembic/env.py` | Modify | Keep explicit user-model import so `Base.metadata` sees the table; auth adds no model |
| `alembic/versions/<revision>_add_user_credentials.py` | Create | Add non-null hash and active columns; downgrade drops them |
| `requirements.txt` | Modify | Add `pwdlib[argon2]`, PyJWT, and `python-multipart` |
| `tests/conftest.py`, `tests/modules/auth/*`, `tests/modules/users/*` | Create/Modify | Test settings, auth behavior, moved validation, public reads, removed POST |

## Interfaces / Contracts

- `POST /auth/register` JSON `{email, full_name, password}` -> `201 UserResponse`.
- `POST /auth/login` form `username=<email>&password=...` -> `200 {access_token, token_type="bearer"}`.
- `GET /auth/me` bearer JWT -> `200 UserResponse`.
- `User` adds `hashed_password: str` and `is_active: bool`; `UserResponse`
  excludes both. Password accepts 8–128 characters and email is stored lowercase.

## Testing Strategy

| Layer | Planned RED coverage | Approach |
|---|---|---|
| Unit | Name/password boundaries, email normalization, real hash verify/failure, JWT subject/expiry/no secrets, invalid/expired token | Pydantic tests; real crypto only in focused security tests |
| Service | Registration duplicate handling; active, wrong, unknown, and inactive login; current-user lookup | Mock/fake SQLAlchemy-facing users operations; assert dummy verification path |
| HTTP | Register responses, OAuth2 form login, `/auth/me`, Spanish 401/403, public GET users, POST users unavailable | `TestClient`, dependency overrides and monkeypatching; no PostgreSQL |
| Migration | Upgrade/downgrade operations and model metadata | Inspect revision/model; run Alembic against local PostgreSQL during verification |

## Threat Matrix

HTTP route safety is covered by RED HTTP tests above: only declared methods
dispatch, missing/invalid bearer credentials fail closed, and former
`POST /users` is unavailable.

| Boundary | Applicability | Design response | Planned RED tests |
|---|---|---|---|
| Documentation-like paths | N/A: no path classification or execution | None | None |
| Git repository selection | N/A: no VCS invocation | None | None |
| Commit state | N/A: no commit automation | None | None |
| Push state | N/A: no push automation | None | None |
| PR commands | N/A: no PR automation | None | None |

## Migration / Rollout

The database is confirmed empty. Add `hashed_password VARCHAR(255) NOT NULL`
and `is_active BOOLEAN NOT NULL DEFAULT true`, then remove the database default
if the generated migration introduces one. Review SQL and run upgrade/downgrade/
upgrade locally. Rollback removes both columns and restores the prior code/routes.

## Open Questions

None.
