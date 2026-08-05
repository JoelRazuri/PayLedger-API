# User Input Validation Specification

## Purpose

Define observable validation and normalization rules for full names submitted
during user creation.

## Requirements

### Requirement: Normalize Outer Whitespace

The system MUST remove leading and trailing whitespace from `full_name` before
validating or persisting it. The system MUST preserve whitespace inside the
normalized value.

#### Scenario: Trim outer whitespace

- GIVEN a user creation request with `full_name` equal to `"  Ana Pérez  "`
- WHEN the request is validated
- THEN the accepted `full_name` is `"Ana Pérez"`

#### Scenario: Preserve internal whitespace

- GIVEN a user creation request with `full_name` equal to `"Ana   Pérez"`
- WHEN the request is validated
- THEN the accepted `full_name` remains `"Ana   Pérez"`

### Requirement: Enforce Normalized Name Length

The system MUST accept a normalized `full_name` containing between 2 and 255
characters, inclusive. It MUST reject shorter or longer values with HTTP status
422 and a validation message in Spanish.

#### Scenario: Accept boundary lengths

- GIVEN a user creation request whose normalized `full_name` has 2 or 255 characters
- WHEN the request is validated
- THEN validation succeeds

#### Scenario: Reject empty or whitespace-only name

- GIVEN a user creation request with an empty or whitespace-only `full_name`
- WHEN the request is validated
- THEN the API responds with HTTP status 422
- AND the validation detail explains the minimum length in Spanish

#### Scenario: Reject one-character name

- GIVEN a user creation request whose normalized `full_name` has 1 character
- WHEN the request is validated
- THEN the API responds with HTTP status 422
- AND the validation detail explains the minimum length in Spanish

#### Scenario: Reject oversized name

- GIVEN a user creation request whose normalized `full_name` has 256 characters
- WHEN the request is validated
- THEN the API responds with HTTP status 422
- AND the validation detail explains the maximum length in Spanish

### Requirement: Accept Unrestricted Name Characters

The system MUST accept Unicode characters without applying an alphabetic
allowlist, provided the normalized value satisfies the length requirement.

#### Scenario: Accept international name characters

- GIVEN a valid `full_name` containing accents, apostrophes, or hyphens
- WHEN the request is validated
- THEN validation succeeds without altering those characters
