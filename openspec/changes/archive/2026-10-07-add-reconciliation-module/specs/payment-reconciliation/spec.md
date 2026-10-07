# Payment Reconciliation Specification

## Purpose

Owners reconcile immutable provider evidence with local payments.

## Requirements

### Requirement: Access

JWT MUST be required for `POST/GET /external-transactions`, `GET /external-transactions/{id}`, `POST /external-transactions/{id}/reconcile`, and `GET /reconciliations[/{id}]`. Owners MUST access only their records; unknown or foreign IDs MUST return HTTP 404.

#### Scenario: Owned access
- GIVEN owned evidence
- WHEN requested
- THEN only owned records are returned

#### Scenario: Foreign access
- GIVEN a foreign ID
- WHEN requested
- THEN response is HTTP 404

### Requirement: Evidence

Evidence MUST accept only canonical terminal status `completed`, `rejected`, `failed`, or `cancelled`, and retain provider, external ID/reference, amount/currency, UTC `occurred_at`, and PayLedger UTC `received_at`.

#### Scenario: Ingest terminal
- GIVEN terminal evidence with UTC occurrence
- WHEN ingested
- THEN both timestamps are UTC

#### Scenario: Reject progressive
- GIVEN `pending` or `processing` evidence
- WHEN ingested
- THEN response is HTTP 422

### Requirement: Idempotency

Evidence MUST be identified by owner/provider/external ID. Exact replay MUST return existing evidence; changed payload MUST return HTTP 409; concurrent exact requests MUST create one record.

#### Scenario: Evidence replay, conflict, concurrency
- GIVEN an ingested external ID
- WHEN exact, changed, or concurrent exact input arrives
- THEN exact input uses one record and changed input returns HTTP 409

### Requirement: Matching

Matching MUST use only owner/provider/external payment reference. Non-null local references MUST be unique per owner/provider, without Payments API change. Evidence without a local payment MUST persist unmatched.

#### Scenario: Preserve unmatched
- GIVEN no matching local payment
- WHEN reconciled
- THEN an unmatched attempt persists

### Requirement: Results

Reconciliation MUST compare amount/currency/status exactly: all equal is `matched`, local difference `mismatched`, no local payment `unmatched`. Attempts MUST immutably retain source IDs; local/external amount/currency/status snapshots; result; `amount_matches`, `currency_matches`, `status_matches`; and UTC `reconciled_at`. Flags MUST be boolean with a local payment; otherwise local snapshots and flags MUST be null.

#### Scenario: Match identical values
- GIVEN evidence and local payment with equal owner/provider/reference/amount/currency/status
- WHEN reconciled
- THEN `matched`, all flags true, and immutable snapshots retained

#### Scenario: Mismatch flags
- GIVEN only currency differs
- WHEN reconciled
- THEN `mismatched`, currency false, other flags true

#### Scenario: Unmatched snapshot
- GIVEN no local payment
- WHEN reconciled
- THEN local snapshots and flags are null

### Requirement: Attempts

Reconciliation MUST require `Idempotency-Key`. Same owner/key/transaction MUST replay; reuse on another transaction MUST return HTTP 409; new key MUST append an immutable attempt; concurrent same-key requests MUST create one.

#### Scenario: Replay or rerun
- GIVEN an attempt with one key
- WHEN same or new key is submitted
- THEN same key replays and new key appends one attempt

#### Scenario: Reuse key
- GIVEN an owner used a reconciliation key
- WHEN used for another transaction
- THEN response is HTTP 409

#### Scenario: Concurrent same key
- GIVEN concurrent same owner/key/transaction requests
- WHEN complete
- THEN exactly one attempt is created and both responses return it

### Requirement: Queries

Queries MUST be owner-scoped. Lists MUST filter `matched`, `mismatched`, or `unmatched`; be stable newest-first; default `limit` to 20 and `offset` to 0; and limit `limit` to 100.

#### Scenario: Filter page
- GIVEN attempts with multiple results
- WHEN valid filter and pagination are requested
- THEN matching attempts are stable newest-first

### Requirement: Validation

The system MUST return HTTP 401 for missing/invalid JWT, HTTP 422 for invalid input/filter/pagination, and HTTP 405 for forbidden mutations. It MUST expose no update/deletion routes; evidence and attempts MUST NOT change after creation.

#### Scenario: Reject invalid
- GIVEN missing JWT, invalid filter, or pagination
- WHEN an endpoint receives it
- THEN response is HTTP 401 or 422 as applicable

#### Scenario: Reject mutation
- GIVEN evidence or attempt
- WHEN PATCH, PUT, or DELETE is requested
- THEN response is HTTP 405 and leaves it unchanged
