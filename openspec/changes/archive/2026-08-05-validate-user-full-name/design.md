# Design: Validate User Full Names

Validate and normalize `full_name` in the Pydantic request schema. This keeps
invalid input outside the service and database layers while preserving FastAPI's
standard `422 Unprocessable Entity` response contract.

## Technical Approach

Add a Pydantic v2 `field_validator` in `UserCreate` that runs before normal type
validation. For string values it trims outer whitespace, checks the normalized
length, and raises Spanish validation errors. Non-string values remain subject
to Pydantic's existing type validation.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|---|---|---|---|
| Validation boundary | `UserCreate` schema | Service or router validation | The rule describes request shape and should fail before business logic or database access. |
| Normalization order | Trim before measuring length | Measure raw input | Limits must apply to the value that would be persisted. |
| Error language | Custom Spanish messages | Pydantic defaults | Matches the project's documented HTTP-message convention. |
| Character policy | No allowlist | Letters-only regular expression | Supports international names and avoids cultural assumptions. |
| Test levels | Schema unit tests plus HTTP validation tests | Database integration tests | The change has no persistence behavior and should not require PostgreSQL. |

## Data Flow

```text
JSON request → UserCreate → trim outer whitespace → length validation
                                              ├─ invalid → HTTP 422
                                              └─ valid   → users service
```

## File Changes

| File | Action | Description |
|---|---|---|
| `app/modules/users/schema.py` | Modify | Normalize and validate `full_name`. |
| `tests/modules/users/test_schema.py` | Create | Cover normalization, limits, and Unicode. |
| `tests/modules/users/test_router.py` | Create | Verify HTTP 422 and Spanish messages. |
| `.gitignore` | Modify | Keep the machine-specific `.atl/` registry local. |

## Interfaces / Contracts

`POST /users` retains its request shape. Valid names are returned and persisted
without outer whitespace. Invalid lengths return FastAPI status `422`; no new
domain exception or database migration is introduced.

## Testing Strategy

| Layer | What to Test | Approach |
|---|---|---|
| Unit | Trimming, internal spaces, 2/255 boundaries, Unicode | Instantiate `UserCreate` directly with Pytest parametrization. |
| Integration | Invalid requests produce Spanish `422` details | Use FastAPI `TestClient`; validation stops before database access. |
| E2E | Not applicable | No external system or persistence change. |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file
classification, or process-integration boundary changes.

## Migration / Rollout

No migration or staged rollout is required. Existing stored names remain
unchanged; the rule applies to new user-creation requests.

## Open Questions

None.
