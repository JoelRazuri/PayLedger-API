# Proposal: Add Authentication

## Intent

Replace passwordless user creation with credential-based authentication. The
new `auth` module owns public registration, login, token issuance, and the
authenticated profile; `users` retains persistence and public reads.

## Scope

### In Scope

- Replace `POST /users` with `POST /auth/register`, which creates an account but
  does not start a session.
- Add OAuth2 form login at `POST /auth/login` and protected `GET /auth/me`.
- Store an Argon2 password hash and active status, normalize email casing, and
  issue JWT access tokens that expire after 30 minutes.
- Keep `GET /users` and `GET /users/{user_id}` public.

### Out of Scope

- Roles, permissions, refresh tokens, token revocation, and server-side logout.
- Password recovery, email verification, and existing-account migration.

## Capabilities

### New Capabilities

- `user-authentication`: Registration, password security, login, JWT access,
  profile retrieval, and inactive-account behavior.

### Modified Capabilities

- `user-input-validation`: Existing full-name validation applies to auth-owned
  registration instead of user creation through `POST /users`.

## Approach

Make `auth` depend one-way on reusable `users` persistence operations. Add
`hashed_password NOT NULL` and `is_active` through Alembic. Use
`pwdlib[argon2]`, PyJWT, and an environment-provided secret. JWT `sub` contains
the user ID. Passwords accept 8–128 characters without composition rules.
Invalid credentials return a Spanish `401`; valid credentials for an inactive
account return a distinct Spanish `403`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/modules/auth/` | New | Auth workflow and routes |
| `app/modules/users/` | Modified | Fields, persistence, and route removal |
| `app/core/`, `app/main.py` | Modified | JWT settings and router |
| `alembic/versions/` | New | Credential migration |
| Dependencies and tests | Modified | Packages and coverage |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Token forgery from exposed secret | Medium | Require environment configuration |
| Credential exposure | Low | Safe schemas and explicit tests |
| Account-state leakage | Medium | Reveal inactivity only after valid credentials |

## Rollback Plan

Revert auth code and dependencies, restore `POST /users`, and run the Alembic
downgrade. The empty database requires no row-preservation strategy.

## Dependencies

- `pwdlib[argon2]`, PyJWT, and `python-multipart`.
- Secure JWT signing secret in the environment.

## Success Criteria

- [ ] Registration persists only a password hash and returns no token or secret.
- [ ] Valid active users can log in and access `/auth/me` for 30 minutes.
- [ ] Invalid credentials return `401`; inactive valid users return `403`.
- [ ] Public user reads remain available and `POST /users` no longer exists.
- [ ] Migration, automated tests, Ruff, and application import succeed.
