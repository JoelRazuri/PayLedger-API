# Design: Add Ledger Module

## Technical Approach

Add a synchronous `ledger` feature using the existing model/schema/service/router pattern and direct SQLAlchemy queries. Payments owns transaction boundaries; Ledger contributes one flush-only completion hook. Providers consume an immutable input snapshot between the committed `processing` claim and a new local finalization transaction.

## Architecture Decisions

| Decision | Choice and rationale | Alternative rejected |
|---|---|---|
| Storage | `JournalEntry` has a direct restrictive Payment FK and snapshots event, `NUMERIC(18,2)` amount, currency, `occurred_at=payment.processed_at`, and UTC persistence `created_at`; its one-to-many `LedgerEntry` relationship preserves traceability. | One denormalized table, which obscures journal cardinality. |
| Vocabulary | Reuse Payments `Currency`; add fixed `payment_completed`, `debit/credit`, and `PAYMENT_EXPENSE/EXTERNAL_FUNDS` enums. | Configurable accounts/FX, outside v1. |
| Integrity | Unique `(payment_id,event_type)` and `(journal_entry_id,side)`, positive amounts, account/side checks, plus PostgreSQL deferred constraint triggers on journal/posting changes validating at commit exactly two siblings, matching header amount/currency, and equal debit/credit. A row `CHECK` cannot aggregate siblings. | Service-only validation or a misleading aggregate `CHECK`. |
| Transaction | `record_completed_payment(db, payment)` adds the journal and two entries, then `flush()` only. Refactor `_complete_processing` into a lock-based finalizer that owns one commit/rollback for status, safe `ProviderResult` fields, UTC `processed_at`, and Ledger. Failure restores persisted `processing`; non-success commits without Ledger. | Ledger committing internally or holding a transaction across provider I/O. |
| Provider boundary | Add frozen `PaymentProviderInput(payment_id: int)` in `payments/provider.py`. `_claim_pending` captures the scalar ID from `UPDATE ... RETURNING` before commit; the provider receives only this detached value. Finalization reloads/locks Payment afterward, preventing `expire_on_commit` attribute access from autobeginning a transaction during I/O while preserving existing outcomes and sandbox IDs. | Passing the expired ORM Payment after commit. |
| Convergence | Lock the payment row during finalization; an identical completed retry returns the existing journal, while conflicting state fails. Uniqueness remains the race backstop. | Catch-and-ignore duplicate inserts, which can hide partial work. |
| Queries | Join Journal to Payment for owner scope; use `EXISTS` for account filtering so pagination returns distinct journals. Stable order is `occurred_at DESC, id DESC`. | Entry joins plus `DISTINCT`, which complicate eager loading/counting. |

## Data Flow

```text
claim + capture immutable input + commit -> provider (no Session access)
 -> reload/lock payment -> apply result -> [success: journal + postings] -> commit
```

## Files

| Action | Paths |
|---|---|
| Create | `app/modules/ledger/{__init__,enums,model,schema,exceptions,service,router}.py`; `alembic/versions/<revision>_create_ledger_tables.py`; `tests/modules/ledger/test_{model,schema,service,router}.py`; `tests/integration/test_ledger_postgres.py`; `tests/alembic/test_ledger_migration.py` |
| Modify | `app/modules/payments/{provider,service}.py`, `app/main.py`, `alembic/env.py`, `tests/modules/payments/test_{provider,service}.py` |
| Delete | None |

## Interfaces / Contracts

`record_completed_payment(db: Session, payment: Payment) -> JournalEntry` never commits or rolls back. `PaymentProvider.process(input: PaymentProviderInput, scenario) -> ProviderResult` preserves controlled outcomes. Routes are `GET /ledger/journals`, `GET /ledger/journals/{journal_id}`, and `GET /ledger/payments/{payment_id}/journal`. `JournalResponse` nests ordered entries; journal and entries expose IDs, fixed vocabulary, exact amounts/currency, and timestamps. Listing accepts `limit=20` (1..100), `offset>=0`, optional `currency` and `account`. Missing/invalid JWT returns `401`; unknown or foreign journal/payment IDs return `404`. No mutation routes exist.

## Testing Strategy

Strict RED -> GREEN -> REFACTOR with `.\.venv\Scripts\python.exe -m pytest`. Unit/router tests cover enums, nesting, filters, `401`, `404` non-disclosure, invalid queries, mutations, frozen provider input, and unchanged sandbox results. A PostgreSQL provider spy captures the Session and asserts `in_transaction() is False` while reading the snapshot; integration also proves deferred rejection of partial/unbalanced journals, atomic rollback to `processing`, non-success absence, and two-session convergence to one journal. Migration tests cycle upgrade/downgrade/upgrade; run Ruff/import checks. Manually verify Swagger before the behavior commit.

## Threat Matrix

| Boundary | Applicability | Safe/failure behavior | Planned RED tests |
|---|---|---|---|
| HTTP routing | Applicable | Missing/invalid JWT -> `401`; unknown/foreign IDs -> `404`; invalid input -> `422`; mutation -> `405` | Every route, auth failures, foreign IDs, invalid filters, POST/PATCH/DELETE |
| Documentation-like paths | N/A: no execution classification | No product-code classifier/executor | None |
| Git repository selection | N/A: no VCS boundary | No repository selection | None |
| Commit state | N/A: no VCS boundary | No index/worktree operation | None |
| Push state | N/A: no VCS boundary | No destination/ref resolution | None |
| PR commands | N/A: no shell/PR automation | No command composition | None |

## Migration / Rollout

Add enums, tables, indexes `(payment_id,event_type)`, `(occurred_at,id)`, `(journal_entry_id,side)`, `(account,journal_entry_id)`, and the deferred trigger; import Ledger metadata in `alembic/env.py`, migrate, then register the router/hook. Downgrade drops trigger/function, entries, journals, and Ledger enums in dependency order. Rollback unregisters hook/router before downgrade; external success remains `processing` for future reconciliation. Final closure archives the complete change folder using the module commit date.

## Open Questions

None blocking.
