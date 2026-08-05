## Exploration: User full-name validation

### Current State

`UserCreate.full_name` accepts any string, including empty or whitespace-only
values, leading/trailing whitespace, and values longer than the database's
255-character column. Validation currently occurs neither in Pydantic nor in the
service layer.

### Affected Areas

- `app/modules/users/schema.py` — define input normalization and constraints.
- `tests/` — add the project's first automated validation tests.

### Approaches

1. **Pydantic field constraints only** — use minimum and maximum lengths.
   - Pros: concise and declarative.
   - Cons: does not reliably reject whitespace-only values after normalization.
   - Effort: Low.

2. **Pydantic constraints plus field validator** — trim outer whitespace and
   validate the normalized value.
   - Pros: keeps request validation at the boundary and supports Spanish errors.
   - Cons: adds a small custom validator.
   - Effort: Low.

3. **Service-layer validation** — reject invalid names in business logic.
   - Pros: reusable outside HTTP.
   - Cons: allows structurally invalid requests past the schema boundary.
   - Effort: Medium.

### Recommendation

Use Pydantic constraints plus a field validator. Trim only outer whitespace,
require 2–255 characters afterward, preserve internal whitespace, allow Unicode
without character restrictions, and keep email normalization out of scope.

### Risks

- Constraints could reject legitimate short names if the minimum is too strict.
- Tests must assert behavior rather than Pydantic's internal error structure.

### Ready for Proposal

Yes. Product rules were confirmed with the user.
