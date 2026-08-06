# Design: Add Payments Module

## Technical Approach

Add a synchronous `payments` feature following the existing model/schema/service/router
shape. The service owns persistence and lifecycle rules; the router supplies the
authenticated user, idempotency header, and sandbox provider dependency, then maps
domain exceptions to Spanish HTTP errors. No repository layer or ledger integration is
introduced.

## Architecture Decisions

| Decision | Choice and rationale | Rejected alternative |
|---|---|---|
| Persistence | One `payments` table embeds the immutable recipient snapshot. This keeps each instruction historically self-contained. | Mutable recipient FK, which could rewrite history. |
| Money/enums | `Decimal` with `NUMERIC(18,2)`, `amount > 0` check, and Pydantic `max_digits=18, decimal_places=2`; Python string enums persist their values through named PostgreSQL enums. | Float or unconstrained strings, which lose exactness or closed-state guarantees. |
| Idempotency | Unique `(owner_id, idempotency_key)` plus SHA-256 of canonical validated input (normalized amount, currency, provider, and recipient fields). Catch insert races, rollback, reload, and compare fingerprints. First creation returns `201`; identical replay returns the same body with `200`; mismatch returns `409`. | Global keys or check-then-insert only, which break owner isolation or race. |
| Processing | Claim with `UPDATE ... WHERE owner_id=? AND id=? AND status='pending' RETURNING`, commit, call provider without an open transaction, then persist one terminal result. | Row lock across provider work, which holds a transaction during external execution. |
| Provider boundary | A synchronous `PaymentProvider` protocol accepts the stored snapshot and sandbox scenario and returns a controlled `ProviderResult`. `SandboxPaymentProvider` is injected with FastAPI `Depends`, enabling deterministic overrides. | Provider logic inside the service/router, which couples tests and HTTP. |
| Failure boundary | Expected sandbox outcomes become `completed`, `rejected`, or `failed`. Interruption or an unexpected exception after claim is not auto-retried and leaves `processing`; only safe code/message fields persist. | Blanket recovery, which could duplicate a provider submission. |

## Data Flow

```text
JWT user -> router -> service -> PostgreSQL
                         | claim + commit
                         v
                 PaymentProvider -> terminal update + commit
```

Create races converge on the owner/key unique constraint. Process and cancel race on
the same conditional `pending` update: one commits; the loser reloads and raises a
state conflict. Foreign and absent IDs share the not-found path. A stranded
`processing` payment remains readable but cannot be processed or cancelled.

## Data Model and Contracts

`Payment` stores: `id`, `owner_id` (FK `users.id`, restricted deletion), key and
fingerprint, `amount`, `currency`, `provider`, `status`, recipient name/account type/
reference/description, nullable provider ID/failure code/failure message, and
timezone-aware created/updated/processed timestamps. Indexes cover
`(owner_id, created_at DESC)`, `(owner_id, status)`, `(owner_id, provider)`, and
`(owner_id, currency)`; the owner/key constraint is also indexed.

Schemas define nested `RecipientInput`, `PaymentCreate`, `PaymentResponse`,
`PaymentProcessRequest`, and bounded/filter query parameters. Response conversion uses
`from_attributes`; no update/delete schema exists. Router mappings are:
`PaymentNotFoundError -> 404 "Pago no encontrado"`, idempotency conflict ->
`409 "La clave de idempotencia ya fue utilizada con otra solicitud"`, and lifecycle/
concurrent/cancel conflict -> `409 "El pago no está disponible para esta acción"`.
Validation messages for invalid monetary, enum, recipient, or scenario input are
Spanish `422` details; services never import FastAPI.

## File Changes

| File | Action | Responsibility |
|---|---|---|
| `app/modules/payments/{enums,model,schema,exceptions}.py` | Create | Domain vocabulary, table, API types, errors |
| `app/modules/payments/{provider,service,router}.py` | Create | Provider port/adapter, use cases, HTTP mapping |
| `app/modules/payments/__init__.py` | Create | Feature package |
| `app/main.py` | Modify | Register payments router |
| `alembic/env.py` | Modify | Import payment metadata |
| `alembic/versions/<revision>_create_payments_table.py` | Create | Enums, table, checks, constraints, indexes, downgrade |
| `tests/modules/payments/test_{model,schema,provider,service,router}.py` | Create | Strict-TDD unit and HTTP behavior |
| `tests/alembic/test_payments_migration.py` | Create | Migration structure and cycle |

## Testing Strategy

Strict TDD uses RED -> GREEN -> REFACTOR. Unit tests cover decimal boundaries,
fingerprint normalization, owner scoping, insert races, filtering, transitions,
provider outcomes, safe metadata, and interruption. Router tests override current user,
database, and provider dependencies to prove authentication, `201/200`, Spanish
`404/409/422`, non-disclosure, and pagination. PostgreSQL integration tests use two
sessions to prove create uniqueness and process/cancel claims. Migration verification
runs on a disposable database: `upgrade head`, `downgrade b73c6cb6e54a`, `upgrade
head`, then imports `app.main`; it asserts enum/table/index removal and recreation.

## Threat Matrix

N/A - no routing, shell, subprocess, VCS/PR automation, executable classification, or
process-integration boundary is introduced.

## Migration / Rollout

Deploy the reversible additive migration before the router. Rollback unregisters the
router, downgrades one revision, and removes the module. Ledger, reconciliation, audit,
workers, and processing recovery remain separate future capabilities.
Use a disposable database for the cycle because the pre-existing credential migration
cannot currently upgrade a populated legacy `users` table.

## Open Questions

None blocking.
