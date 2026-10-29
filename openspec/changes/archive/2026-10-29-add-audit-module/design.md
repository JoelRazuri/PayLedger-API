# Design: Add Audit Module

## Technical Approach

Add an `audit` feature module following the existing model/schema/service/router layout. Mutation services stage audit events in the same SQLAlchemy transaction as the corresponding persisted outcome while preserving existing lifecycle commits. Known authenticated business exceptions first roll back, then persist a failure event in a new transaction before re-raising. Read endpoints remain owner-scoped through the JWT-derived `User.id`.

## Architecture Decisions

| Decision | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| Transaction ownership | Preserve current lifecycle boundaries. Stage each event before the commit that persists its corresponding outcome; after business exceptions, perform `rollback`, a new audit transaction, then re-raise. | Router middleware; asynchronous/outbox audit | Services know outcomes and resource IDs. This provides atomic evidence without changing recovery, concurrency, or HTTP behavior. |
| Audit contract | Typed `AuditAction`, `AuditResourceType`, and `AuditOutcome` enums plus an `AuditEventData` command accepted by `stage_event`; details are built by action-specific allowlist helpers. | Free-form strings/details; storing request bodies | Closed values prevent ambiguous evidence, and server-owned builders prevent tokens, raw bodies, and provider payloads from leaking. |
| Resource references | Store `resource_type` and nullable `resource_id`; validate supported combinations in the audit service, without cross-table foreign keys. | One nullable FK per resource; JSON-only identity | Matches the polymorphic requirement without coupling the audit table to every domain table. |
| Immutability | PostgreSQL trigger rejects `UPDATE` and `DELETE`; application exposes read routes only. | ORM convention alone; permissions only | Database enforcement covers accidental and direct mutations. |
| Query shape | Offset/limit pagination and composable owner, action, resource type/ID, outcome, and inclusive UTC-range filters; order by `occurred_at DESC, id DESC`. | Cursor pagination; global/admin query | Matches existing API conventions and guarantees deterministic owner-private results. |

## Data Flow

```text
payment.process -> claim PROCESSING -> COMMIT -> provider -> final state + audit -> COMMIT
scoped action --------------------------------------\-> business error -> ROLLBACK
                                                                      -> failure audit -> COMMIT -> re-raise

GET /audit-events -> JWT actor -> owner-filtered audit query -> response
```

`payment.process` retains its durable `PROCESSING` claim before provider I/O. The final provider result, ledger entry when applicable, and audit event share the following transaction. Provider exceptions preserve the committed claim and remain unaudited as infrastructure failures. Concurrent callers retain current single-claim behavior; losing state conflicts are audited after rollback. Provider `rejected`/`failed` results commit atomically with `outcome=failure`. Valid idempotent replays commit a distinct success event with `details={"replayed": true}`.

## File Changes

| File | Action | Description |
|---|---|---|
| `app/modules/audit/enums.py`, `model.py`, `schema.py`, `service.py`, `router.py`, `exceptions.py` | Create | Persistence, allowlisted event commands, filters, owner-scoped reads, and 404 mapping. |
| `app/modules/payments/service.py` | Modify | Stage create/process/cancel outcomes at existing commit boundaries and persist known failures after rollback. |
| `app/modules/reconciliation/service.py` | Modify | Stage ingestion/reconciliation outcomes, including concurrent replays and conflicts. |
| `app/main.py`, `alembic/env.py` | Modify | Register the read router and audit metadata. |
| `alembic/versions/a7d3c2e9f1b6_add_audit_events.py` | Create | Add enums/table/indexes/FK/checks and the immutable trigger with reversible downgrade. |
| `tests/modules/audit/`, `tests/modules/payments/test_service.py`, `tests/modules/reconciliation/test_service.py` | Create/Modify | Unit and route behavior, allowlists, outcomes, replay, and failure transactions. |
| `tests/integration/test_audit_postgres.py`, `tests/alembic/test_audit_migration.py` | Create | Atomicity, isolation, concurrency, trigger enforcement, and migration cycle. |

## Interfaces / Contracts

`AuditEvent`: `id`, `actor_id -> users.id`, `action`, `resource_type`, `resource_id?`, `outcome`, `reason_code?`, JSONB `details`, and timezone-aware `occurred_at`. Database checks require `reason_code` exactly for failures. Details allow only `replayed`, payment `status`, and reconciliation `result`, as applicable. The read-only list accepts `limit`, `offset`, `action`, `resource_type`, `resource_id`, `outcome`, `occurred_from`, and `occurred_to`; detail returns `404` for missing or foreign rows.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | Contracts, filters, allowlists, mappings, staged outcomes, rollback/failure, replay, provider exception | Strict TDD with SQLAlchemy mocks and FastAPI dependency overrides. |
| Integration | Final-result atomicity, durable claim after provider exception, concurrent-process conflict auditing, replay events, isolation, UTC filters, immutable writes | PostgreSQL sessions and HTTPX/TestClient against real constraints. |
| Migration | Named reversible schema and trigger | Structural assertions plus upgrade/downgrade runtime cycle. |

## Threat Matrix

The HTTP router changes do not introduce the tool/process boundaries covered by this matrix.

| Boundary | Applicability | Design response | Planned RED tests |
|---|---|---|---|
| Documentation-like paths | N/A: no executable-file classification | None | None |
| Git repository selection | N/A: no Git execution | None | None |
| Commit state | N/A: no VCS automation | None | None |
| Push state | N/A: no push integration | None | None |
| PR commands | N/A: no PR automation | None | None |

## Migration / Rollout

Deploy the migration before application code. Downgrade removes the trigger, function, table, and audit enums. If production events exist, preserve/export evidence before rollback.

## Open Questions

None.
