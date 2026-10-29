# Delta for Payment Reconciliation

## ADDED Requirements

### Requirement: Reconciliation audit outcomes

Authenticated evidence ingestion and reconciliation execution MUST emit `external_transaction.ingest` and `reconciliation.execute` outcomes under Financial Audit without changing API or matching behavior.

#### Scenario: Ingestion outcomes
- GIVEN authenticated valid evidence, exact replay, or business conflict
- WHEN ingestion is handled
- THEN it is audited; replay is marked success and conflict failure has a reason

#### Scenario: Execution outcomes
- GIVEN reconciliation yields matched, mismatched, unmatched, replay, or business failure
- WHEN executed
- THEN its outcome is audited without changing the API result

#### Scenario: Concurrent replay
- GIVEN concurrent exact ingestion requests
- WHEN one creates evidence and another replays
- THEN each has a success event and replay is marked

#### Scenario: Transaction boundary
- GIVEN successful reconciliation or failure after rollback
- WHEN persisted
- THEN success is atomic with its event and failure evidence survives rollback
