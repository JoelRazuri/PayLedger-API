# Ledger Journals Specification

## Purpose

Immutable journals for completed-payment discovery.

## Requirements

### Requirement: Completed Payment Journaling

The system MUST create one `payment_completed` journal only when a payment completes. Failed, rejected, and cancelled payments MUST NOT create journals. Local completion, journal, and postings MUST succeed together; on local failure, the payment MUST remain `processing` and no journal or posting SHALL be visible.

#### Scenario: Completed payment creates a journal

- GIVEN an owned payment in `processing`
- WHEN it completes with a processed event time
- THEN one journal is available for that payment

#### Scenario: Non-success state creates none

- GIVEN an owned payment becoming failed, rejected, or cancelled
- WHEN it is finalized
- THEN no journal is available

#### Scenario: Posting failure preserves processing

- GIVEN an owned payment in `processing`
- WHEN both postings cannot be created locally
- THEN it remains `processing` with no journal or posting

### Requirement: Idempotent Journal Identity

The system MUST expose at most one journal per `(payment, event_type)` pair, including concurrent or retried completion processing.

#### Scenario: Duplicate completion race

- GIVEN concurrent or retried completion for one payment
- WHEN both attempts finish
- THEN exactly one `payment_completed` journal is available

### Requirement: Balanced Immutable Postings

Each journal MUST contain exactly two immutable postings in the payment currency: debit `PAYMENT_EXPENSE` and credit `EXTERNAL_FUNDS`. Both amounts and the currency MUST equal the payment values, and debit MUST equal credit. The system MUST NOT expose manual journals, refunds, reversals, fees, configurable accounts, FX, balances, organizations, or additional postings.

#### Scenario: Completed payment is balanced

- GIVEN a completed payment with amount and currency
- WHEN its journal is retrieved
- THEN it has equal required postings

#### Scenario: Journal facts cannot change

- GIVEN an existing journal and postings
- WHEN a client attempts to alter or remove them
- THEN mutation is unavailable and facts remain unchanged

### Requirement: Payment Trace and Timestamps

A journal MUST directly identify its payment. `occurred_at` MUST equal the UTC processed event time; `created_at` MUST be the UTC local persistence time.

#### Scenario: Journal retains payment timing

- GIVEN a payment with a processed event time
- WHEN its journal is retrieved
- THEN it identifies the payment and returns the required UTC timestamps

### Requirement: Owner-Scoped Read API

The system MUST require JWT authentication for listing and lookup by journal or payment. A caller MAY access only its own journals; foreign journal or payment IDs MUST return `404`. The API MUST be read-only and MUST NOT expose creation or mutation operations.

#### Scenario: Owner reads journal

- GIVEN an authenticated owner with a journal
- WHEN it is listed or looked up by journal or payment ID
- THEN the journal is returned

#### Scenario: Foreign access is undisclosed

- GIVEN an authenticated non-owner with another owner's ID
- WHEN the non-owner performs a lookup
- THEN the response is `404`

#### Scenario: Mutation is unavailable

- GIVEN an authenticated caller
- WHEN the caller attempts journal creation, update, or deletion
- THEN no mutation operation is available

### Requirement: Journal Listing

The system MUST list distinct owner journals newest first with `limit` and `offset`. `limit` MUST default to 20 and MUST NOT exceed 100. Currency and account filters MUST be supported; invalid pagination or filter values MUST be rejected.

#### Scenario: Filtered paginated list

- GIVEN an authenticated owner with journals
- WHEN listing with valid pagination and currency or account filters
- THEN only matching distinct journals are returned newest first

#### Scenario: Invalid list values

- GIVEN an authenticated caller
- WHEN invalid limit, offset, currency, or account filters are supplied
- THEN the request is rejected

#### Scenario: Missing journal

- GIVEN an authenticated owner
- WHEN an unknown journal or payment ID is looked up
- THEN the response is `404`