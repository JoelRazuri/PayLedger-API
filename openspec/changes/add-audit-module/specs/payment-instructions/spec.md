# Delta for Payment Instructions

## ADDED Requirements

### Requirement: Payment audit outcomes

Authenticated payment create, process, and cancel attempts MUST emit `payment.create`, `payment.process`, and `payment.cancel` outcomes under Financial Audit without changing API or lifecycle behavior.

#### Scenario: Business outcomes
- GIVEN an authenticated create, process, or cancel succeeds or has a business failure
- WHEN handled
- THEN the matching success/failure event is recorded without changing the API result

#### Scenario: Replay and conflict
- GIVEN an idempotent create replay or business conflict
- WHEN handled
- THEN replay is audited as marked success and conflict as failure with reason

#### Scenario: Concurrent create
- GIVEN concurrent identical create requests
- WHEN one creates and another replays
- THEN both requests have success events and the replay is marked

#### Scenario: Transaction boundary
- GIVEN successful mutation or failure after rollback
- WHEN persisted
- THEN success is atomic with its event and failure evidence survives rollback
