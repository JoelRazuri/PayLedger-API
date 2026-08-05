# Proposal: Validate User Full Names

## Intent

Prevent invalid names from reaching the service or PostgreSQL. The current API
accepts empty, whitespace-only, and oversized values, while the database allows
at most 255 characters.

## Scope

### In Scope

- Trim leading and trailing whitespace from `full_name`.
- Require 2–255 characters after trimming, with Spanish validation messages.
- Preserve internal whitespace and accept unrestricted Unicode characters.
- Add automated tests for valid, normalized, and invalid inputs.

### Out of Scope

- Email normalization or validation changes.
- Character allowlists, title casing, or internal whitespace normalization.
- Database model or migration changes.

## Capabilities

### New Capabilities

- `user-input-validation`: Observable validation and normalization rules for
  user registration input.

### Modified Capabilities

None.

## Approach

Add declarative Pydantic constraints and a field validator to `UserCreate`.
Implement through strict TDD: failing schema and API tests first, followed by the
minimum validation code.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `app/modules/users/schema.py` | Modified | Validate normalized full names. |
| `tests/` | New | Cover accepted, normalized, and rejected requests. |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| Legitimate one-character names are rejected | Medium | The two-character minimum is an explicit product decision. |
| Tests couple to Pydantic internals | Low | Assert HTTP status and stable message content only. |

## Rollback Plan

Revert the schema validator and its tests. No persisted data or database schema
requires rollback.

## Dependencies

- Existing Pydantic v2, FastAPI, HTTPX, and Pytest dependencies.

## Success Criteria

- [ ] Names of 2–255 characters are accepted after outer trimming.
- [ ] Empty, whitespace-only, one-character, and oversized names are rejected.
- [ ] Internal whitespace and Unicode characters remain accepted.
- [ ] Ruff and the complete Pytest suite pass.
