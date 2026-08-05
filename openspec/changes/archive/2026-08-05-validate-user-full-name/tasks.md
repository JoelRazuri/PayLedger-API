# Tasks: Validate User Full Names

## Review Workload Forecast

| Field | Value |
|---|---|
| Estimated changed lines | 450–650 including SDD artifacts |
| 400-line budget risk | High |
| Chained PRs recommended | No |
| Suggested split | Single delivery with separate SDD foundation and feature commits |
| Delivery strategy | exception-ok |
| Chain strategy | size-exception |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: size-exception
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|---|---|---|---|---|---|
| 1 | Initialize and document SDD change | Commit 1 | Parse OpenSpec YAML and run `ruff check .` | N/A — documentation/config only | `.gitignore` and `openspec/config.yaml` |
| 2 | Deliver validated user names | Commit 2 | `python -m pytest tests/modules/users -q` | `TestClient` invalid-name request returns 422 | User schema, tests, specification, verification, and archived change |

## Phase 1: RED — Executable Specification

- [x] 1.1 Create `tests/modules/users/test_schema.py` covering trimming, internal whitespace, 2/255 boundaries, invalid lengths, and Unicode.
- [x] 1.2 Create `tests/modules/users/test_router.py` proving invalid names return HTTP 422 with Spanish detail.
- [x] 1.3 Run focused tests and record the expected failures before production changes.

## Phase 2: GREEN — Minimum Implementation

- [x] 2.1 Add the Pydantic v2 `full_name` validator to `app/modules/users/schema.py`.
- [x] 2.2 Run focused tests until all specified scenarios pass.

## Phase 3: REFACTOR and Verification

- [x] 3.1 Review names and duplication without changing behavior, then rerun focused tests.
- [x] 3.2 Run the full Pytest suite, Ruff, and the application import check.
- [x] 3.3 Persist apply evidence and hand the completed tasks to independent SDD verification.
