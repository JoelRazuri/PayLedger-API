## Exploration: Authentication and auth-owned registration

### Current State
PayLedger exposes `POST /users` for public user creation and keeps the creation
schema, duplicate-email handling, persistence, and HTTP translation in the
`users` feature. The `users` table has no credential or activation columns.
There is no `auth` module, token configuration, authentication dependency, or
installed password-hashing/JWT package. `GET /users` and `GET /users/{user_id}`
are currently public.

The project context already anticipates email/password authentication, JWT,
`hashed_password`, `is_active`, `/auth/login`, `/auth/me`, and
`get_current_user`. The current request additionally establishes
`POST /auth/register` as the public registration endpoint and intends to remove
public creation from the `users` router.

The current database may contain rows created without credentials. Adding a
non-null `hashed_password` column therefore requires an explicit data strategy;
a valid password hash cannot be safely invented for an existing user.

### Affected Areas
- `app/main.py` — register the new auth router.
- `app/core/settings.py` — load a signing secret, JWT algorithm, and access-token lifetime from configuration.
- `app/modules/auth/` — own registration and login schemas, password operations, JWT creation/decoding, authentication dependencies, HTTP routes, and auth-specific exceptions.
- `app/modules/users/model.py` — persist `hashed_password` and, if confirmed, `is_active` without exposing either in API responses.
- `app/modules/users/schema.py` — stop treating the current passwordless `UserCreate` as a public registration contract; keep reusable user response schemas.
- `app/modules/users/service.py` — retain user lookup/persistence primitives while removing passwordless public creation or adapting it for auth orchestration.
- `app/modules/users/router.py` — remove `POST /users`; decide whether read endpoints become authenticated in this change.
- `alembic/versions/` — add and manually review the credential/activation migration, including existing-row behavior and downgrade safety.
- `requirements.txt` — add password hashing and JWT dependencies; none are currently installed.
- `tests/modules/auth/` — cover registration, hashing, login success/failure, token claims/expiry, current-user resolution, inactive users if included, and sensitive-data exclusion.
- `tests/modules/users/` — remove or relocate creation-route tests and preserve name-validation coverage under the registration contract.
- `openspec/specs/user-input-validation/spec.md` — its observable behavior currently says “user creation”; the delta should make clear that registration preserves these rules.

### Approaches
1. **Dedicated auth workflow over user persistence primitives** — `auth` owns public credential workflows and depends one-way on reusable `users` lookups and persistence.
   - Pros: Matches the requested feature boundary; keeps HTTP concerns in routers; prevents passwordless user creation; avoids a circular dependency; leaves the user entity reusable by future modules.
   - Cons: Requires carefully naming internal user operations so they are not mistaken for public registration; touches both modules and existing tests.
   - Effort: High

2. **Thin auth router delegating registration to the existing users service** — move only the endpoint while expanding `UserCreate` and `create_user` with password hashing.
   - Pros: Fewer files and a smaller initial diff; reuses the current flow directly.
   - Cons: Credential policy and hashing remain owned by `users`; the module boundary becomes cosmetic; future login/security behavior is split across features.
   - Effort: Medium

3. **Adopt a full authentication framework** — use a package that provides registration, JWT, and user management abstractions.
   - Pros: More built-in functionality and established extension points.
   - Cons: Introduces substantial abstractions and conventions into a small educational codebase; conflicts with the current simple service/router architecture; obscures the mechanics the project intends to teach.
   - Effort: High

### Recommendation
Use the dedicated auth workflow. Create `POST /auth/register`,
`POST /auth/login`, and `GET /auth/me`; remove `POST /users`; let `auth` depend
on `users`, never the reverse. The auth layer should hash and verify passwords,
issue and validate short-lived bearer access tokens, and return the existing
safe `UserResponse`. The JWT `sub` should be the immutable user ID encoded as a
string, not the mutable email.

Use `pwdlib[argon2]` with its recommended Argon2 settings and PyJWT. This is the
current FastAPI-documented combination, both projects declare Python 3.14
support, and it avoids introducing a full authentication framework. Keep JWT
configuration in `Settings`, with the signing secret supplied only through the
environment. Use a dummy password hash when the submitted email does not exist
so failed login timing does not trivially reveal account existence. Return the
same Spanish 401 response for an unknown email and a wrong password.

Registration should own a new password-bearing input schema while reusing the
existing full-name validation. The plaintext password must be used only during
validation/hashing and must never be persisted, logged, placed in a JWT, or
included in a response. Keep access-token scope small for this first iteration;
refresh tokens, password recovery, email verification, roles, and revocation
can be separate changes.

Before proposal, confirm these scope decisions:

- How should the migration handle existing passwordless rows: reset local user
  data, add a temporary nullable column for a later credential-setup flow, or
  use another explicit migration path?
- Should `is_active` and inactive-user rejection be included now, as anticipated
  by `PROJECT_CONTEXT.md`, or deferred?
- What password policy should registration enforce (recommended baseline: 8 to
  128 characters, without composition rules)?
- Should `/auth/login` accept OAuth2 form fields (`username` containing the
  email) for Swagger's standard Authorize flow, or a JSON body with `email` and
  `password`? OAuth2 form handling would also require `python-multipart`.
- What access-token lifetime should be used (recommended baseline: 30 minutes)?
- Should the existing user read endpoints remain public during this change, or
  should they require a valid active user immediately?

### Risks
- A non-null credential migration can fail or silently lock out existing users if its data strategy is not decided first.
- Removing `POST /users` is an intentional API-breaking change for any existing client, although no client is present in this repository.
- Weak or committed JWT secrets would allow token forgery; startup configuration and documentation must prevent insecure defaults.
- Authentication failures can leak account existence through different messages or substantially different code paths.
- JWT access tokens are not encrypted or individually revocable; sensitive data must not enter claims, and a short expiration limits exposure.
- Hashing parameters can make tests slow; tests should exercise real hashing selectively and isolate unrelated route behavior.
- Email uniqueness is currently case-sensitive in PostgreSQL, so differently cased versions of the same email may create separate identities unless normalization is addressed explicitly.

### Ready for Proposal
No — the architecture and library direction are ready, but the orchestrator
should first ask the user to decide the existing-user migration strategy,
`is_active` scope, password rules, login request format, token lifetime, and
whether user read endpoints become protected in this change.
