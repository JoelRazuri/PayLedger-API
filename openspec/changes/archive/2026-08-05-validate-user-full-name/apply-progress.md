# Apply Progress: Validate User Full Names

## Status

All 8 implementation tasks are complete in Strict TDD mode. The change is ready
for independent SDD verification.

## Completed Tasks

- [x] Added schema tests for normalization, boundaries, invalid lengths, and Unicode.
- [x] Added HTTP tests proving invalid input returns Spanish `422` details.
- [x] Captured behavioral RED before changing production code.
- [x] Added the Pydantic v2 validator and confirmed GREEN.
- [x] Reviewed the implementation and ran all quality checks.

## TDD Cycle Evidence

| Task | Test File | Layer | Safety Net | RED | GREEN | TRIANGULATE | REFACTOR |
|---|---|---|---|---|---|---|---|
| 1.1 | `test_schema.py` | Unit | N/A — new file | ✅ Written first | ✅ Passed, 9 cases | ✅ Boundaries and Unicode | ✅ Names reviewed |
| 1.2 | `test_router.py` | Integration | N/A — new file | ✅ Written first | ✅ Passed, 4 cases | ✅ Minimum and maximum failures | ✅ Mock kept at boundary |
| 1.3 | Both | Mixed | App import and Ruff passed | ✅ Written; 9 failed, 4 passed | ✅ Passed, 13 cases | ✅ Seven scenarios represented | ➖ N/A |
| 2.1 | Both | Mixed | RED captured | ✅ Written before production change | ✅ Passed, 13 cases | ✅ Different branches exercised | ✅ Validator remains focused |
| 2.2 | Both | Mixed | RED captured | ✅ Written; see task 1.3 | ✅ Passed, 13 cases | ✅ 13 parameter cases | ➖ None needed |
| 3.1 | Both | Mixed | 13 passed | ✅ Written in prior RED tasks | ✅ Passed, 13 cases | ✅ Existing cases retained | ✅ No further change needed |
| 3.2 | Full suite | Mixed | 13 passed | ✅ Written in prior RED tasks | ✅ Passed, 13 cases | ✅ Schema and HTTP layers | ✅ Ruff clean |
| 3.3 | SDD artifacts | Structural | All checks green | ✅ Written and recorded | ✅ Evidence checks pass | ➖ Structural task | ➖ None needed |

## Test Summary

- Total tests written: 13 parameterized cases.
- Total tests passing: 13.
- Layers used: unit 9, integration 4, E2E 0.
- Approval tests: none; behavior was intentionally changed through RED tests.
- Pure functions created: none; validation belongs to the Pydantic schema.

## Work Unit Evidence

| Evidence | Result |
|---|---|
| Focused tests | `.\\.venv\\Scripts\\python.exe -m pytest tests\\modules\\users -q` → exit 0, 13 passed |
| Runtime harness | `python -m pytest tests/modules/users/test_router.py -q` → exit 0, 4 HTTP cases passed |
| Full suite | `python -m pytest -q` → exit 0, 13 passed |
| Static analysis | `ruff check .` → exit 0, all checks passed |
| Application import | `python -c "import app.main"` → exit 0 |
| Rollback boundary | Revert `schema.py` validator and `tests/modules/users/`; no database or persisted-data rollback |

## Deviations

The Pytest command changed from direct `pytest.exe` execution to
`python -m pytest` because the direct executable did not include the repository
root on the import path. No behavioral or architectural deviation occurred.

## Issues Found

The initial test command failed during collection with `ModuleNotFoundError`.
After correcting the runner command, behavioral RED was 9 failed and 4 passed.
