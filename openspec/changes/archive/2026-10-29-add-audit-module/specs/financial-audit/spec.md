# Financial Audit Specification

## Purpose

Immutable evidence for scoped financial actions.

## Requirements

### Requirement: Scoped event capture

The system MUST record authenticated `payment.create`, `payment.process`, `payment.cancel`, `external_transaction.ingest`, and `reconciliation.execute` attempts. Events MUST include JWT actor (user FK), action, closed resource type, optional resource ID, business outcome, UTC time, and allowlisted details. Failures require a reason; pre-creation failures MAY have null resource ID. Provider rejection/failure is failure; valid replay is success with `details.replayed=true`. GET, registration/login, malformed input, invalid/missing JWT, generic 422, infrastructure/security failures, and unlisted flows MUST NOT be audited.

#### Scenario: Success, replay, or failure
- GIVEN an authenticated scoped operation succeeds, replays, or fails for a business reason
- WHEN handled
- THEN its event reflects the outcome; replay is marked and failure has a reason

#### Scenario: Excluded request
- GIVEN an excluded, unauthenticated, or read-only request
- WHEN handled
- THEN no event is created

### Requirement: Durable, private, append-only evidence

Successful changes and events MUST commit atomically; authenticated business-failure events MUST survive rollback in a separate transaction. Events MUST be append-only with no public write API. Resources use polymorphic identity without cross-table foreign keys. Details MUST be allowlisted and exclude secrets, tokens, and raw bodies.

#### Scenario: Transaction failure
- GIVEN success or a business failure after domain rollback
- WHEN persistence completes
- THEN success and event commit together, while failure event remains durable

#### Scenario: Safe storage
- GIVEN arbitrary sensitive request/provider data or a mutation attempt
- WHEN event data is stored or changed
- THEN unallowlisted data is absent and mutation is rejected

### Requirement: Owner-scoped discovery

JWT-authenticated `GET /audit-events` and `GET /audit-events/{id}` MUST expose only the actor's events. Lists MUST provide pagination and action, resource, outcome, and UTC range filters. Unknown and foreign IDs MUST both return 404.

#### Scenario: Filtered list
- GIVEN events with different owners, actions, resources, outcomes, and times
- WHEN an owner lists using filters and pagination
- THEN only matching owned events are returned

#### Scenario: Non-disclosure
- GIVEN a foreign or absent event ID
- WHEN detail is requested
- THEN both return 404

### Requirement: Database immutability

PostgreSQL MUST reject event UPDATE and DELETE.

#### Scenario: Reject mutation
- GIVEN a persisted event
- WHEN UPDATE or DELETE is attempted
- THEN the database rejects it and preserves the event
