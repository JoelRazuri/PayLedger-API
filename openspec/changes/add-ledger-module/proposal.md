# Proposal: Add Ledger Module

## Intent

Give client companies an immutable internal accounting view for reconciliation. PayLedger records company-reported operations and compares them with banks, providers, or processors; it never custodies or transfers money. Payments owns operational history, Audit owns action/state history, and Ledger records only real accounting impact.

## Scope

### In Scope

- Automatically create one journal only when a Payment becomes `completed`; `failed`, `rejected`, and `cancelled` create none.
- Persist `journal_entries` accounting facts with direct `payment_id -> payments.id`, plus one-to-many `ledger_entries` postings. Enforce `(payment_id,event_type)` uniqueness with `event_type=payment_completed`.
- Create exactly two equal postings using the payment's amount and currency: debit `PAYMENT_EXPENSE`, credit `EXTERNAL_FUNDS`. Each journal has one currency; no FX.
- Provide an authenticated, immutable, read-only API to list journals, get one by ID, and get one for a payment. Foreign IDs return `404`. Listing uses limit/offset (default 20, maximum 100), newest first, with optional currency/account filters.
- Store UTC `occurred_at` from `payment.processed_at` and `created_at` when the journal persists.

### Out of Scope

- Manual journals, reversals/refunds, fees/taxes, configurable accounts, FX, balances/advanced reports, organizations/roles, and more than two postings.
- Payment operations, Audit history, reconciliation recovery, or external rollback.

## Capabilities

### New Capabilities

- `ledger-journals`: Automatic balanced accounting for completed payments and authenticated read-only journal discovery.

### Modified Capabilities

- None. Payment completion integration belongs to this new contract; no current main specification changes.

## Approach

Add a Ledger model/schema/service/router and additive migration. Successful local finalization atomically commits `processing -> completed`, one journal, and both postings. Journal failure rolls back local completion, leaving the payment `processing`; external success cannot roll back, so future reconciliation handles the mismatch.

## Affected Areas

- `app/modules/ledger/`: new accounting model, queries, schemas, and API.
- `app/modules/payments/service.py`: modified atomic successful finalization.
- `app/main.py`, `alembic/versions/`: router registration and schema.
- `tests/modules/ledger/`, `tests/modules/payments/`: strict-TDD coverage.

## Risks

- **Duplicate accounting (Medium):** database uniqueness and transactional insertion.
- **External/local mismatch (Medium):** retain `processing`; defer recovery to reconciliation.
- **Unbalanced postings (Low):** fixed posting rule plus database/service invariants.

## Rollback Plan

Disable the Ledger router and completion hook, then downgrade the additive migration. Preserve external payment facts; never fabricate rollback journals.

## Dependencies

- Authenticated Payments, PostgreSQL transactions, and `payment.processed_at`.
- Strict TDD via `.\.venv\Scripts\python.exe -m pytest`; manual verification precedes behavior commits.

## Success Criteria

- [ ] Each successful finalization atomically creates exactly one balanced, immutable journal; other terminal states create none.
- [ ] Authenticated queries enforce ownership, filters, ordering, pagination, timestamps, and `404` non-disclosure.
- [ ] Tests, migration cycle, Ruff, import, and manual verification pass; closure moves the full change folder into an archive dated with the last module commit.
