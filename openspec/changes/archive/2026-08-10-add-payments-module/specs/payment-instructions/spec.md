# Payment Instructions Specification

## Requirements

### Requirement: Authentication

Payment actions MUST require JWT authentication; unauthenticated requests MUST be rejected.

#### Scenario: Unauthenticated
- GIVEN no JWT
- WHEN a payment action is requested
- THEN it is rejected

### Requirement: Creation and snapshots

Owners MUST create outgoing ARS/USD payments with exact positive amounts of no more than two decimals and only `mercado_pago`, `uala`, or `stripe`. Recipient snapshots MUST include name, account type (`bank_account`, `virtual_wallet`, or `provider_account`), reference, optional description; they MUST NOT change or be deleted.

#### Scenario: Create
- GIVEN an owner supplies valid recipient, money, provider
- WHEN the owner creates a payment
- THEN an owned `pending` payment retains that snapshot

#### Scenario: Invalid values
- GIVEN money or provider is invalid
- WHEN the owner creates a payment
- THEN it is rejected without a payment

#### Scenario: Immutability
- GIVEN a payment exists
- WHEN its recipient changes or mutation/deletion is attempted
- THEN payment and snapshot remain unchanged

### Requirement: Idempotent creation

The system MUST require an owner-scoped `Idempotency-Key`, replay the original payment for an identical request, and return `409` for the same owner's key with a different payload.

#### Scenario: Replay
- GIVEN an owner previously used an idempotency key
- WHEN the identical request is repeated
- THEN the original payment returns

#### Scenario: Key conflict
- GIVEN an owner previously used an idempotency key
- WHEN the payload changes
- THEN the request returns `409` without a payment

#### Scenario: Independent owner keys
- GIVEN different owners use the same idempotency key
- WHEN each creates a valid payment
- THEN their keys and payments remain independent

### Requirement: Discovery

The system MUST return only owned payments. It MUST support limit/offset pagination (default 20, maximum 100) and status, provider, and currency filters, newest first. Foreign or nonexistent identifiers MUST return `404` without disclosing ownership.

#### Scenario: List
- GIVEN an owner has varied payments
- WHEN listing with filters and pagination
- THEN matches are newest first in that page

#### Scenario: Non-disclosure
- GIVEN a payment belongs to another owner
- WHEN it is read, processed, or cancelled
- THEN the operation returns `404`

### Requirement: Lifecycle

New payments MUST be `pending`. Process and cancel MUST be allowed only from `pending`; generic state changes are forbidden. Process MAY produce `completed`, `rejected`, or `failed`; these and `cancelled` are terminal and MUST NOT transition. Unavailable actions MUST return `409`.

#### Scenario: Cancel
- GIVEN an owner has a pending payment
- WHEN it is cancelled
- THEN it becomes `cancelled`

#### Scenario: Invalid action
- GIVEN a payment is processing or terminal
- WHEN its owner requests process or cancel
- THEN it returns `409` and keeps its state

### Requirement: Synchronous sandbox processing

The process action MUST accept only `success`, `business_rejection`, or `technical_failure` and execute synchronously. It MUST atomically claim `pending` as `processing` before provider work; concurrent processing MUST return `409`. Interruption after claiming MUST leave it `processing`, without automatic recovery or another provider call.

#### Scenario: Outcomes
- GIVEN an owner submits each allowed sandbox scenario for a pending payment
- WHEN it is processed
- THEN it becomes `completed`, `rejected`, or `failed` respectively

#### Scenario: Concurrency
- GIVEN a process request claimed the payment
- WHEN another process request arrives
- THEN it returns `409`

#### Scenario: Stranded claim
- GIVEN processing is interrupted after its claim
- WHEN later read
- THEN it remains `processing` without automatic retry or recovery

### Requirement: Safe provider results

The system MUST omit `provider_payment_id` until supplied. It MUST record `processed_at` plus controlled `failure_code` and safe `failure_message` for rejection/failure; it MUST NOT persist or expose raw provider payloads.

#### Scenario: Controlled results
- GIVEN sandbox returns outcome data, provider ID, and raw details
- WHEN processing completes
- THEN it exposes that ID, applicable controlled metadata, and no raw payload