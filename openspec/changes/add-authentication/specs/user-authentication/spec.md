# User Authentication Specification

## Purpose

Define observable registration, authentication, token, and profile behavior.

## Requirements

### Requirement: Register an Account Safely

The system MUST expose `POST /auth/register`, lowercase emails, accept passwords
of 8 to 128 characters inclusive, and create active accounts. It MUST NOT store
plaintext passwords or return passwords, password hashes, or access tokens.

#### Scenario: Register valid account

- GIVEN valid data with a mixed-case email and valid password
- WHEN the client registers
- THEN the API creates an active account with a normalized lowercase email
- AND returns safe user data without credentials or token

#### Scenario: Enforce password boundaries

- GIVEN a password of 8 or 128 characters
- WHEN the client registers
- THEN registration succeeds

#### Scenario: Reject invalid password length

- GIVEN a password shorter than 8 or longer than 128 characters
- WHEN the client registers
- THEN the API responds with HTTP status 422

#### Scenario: Reject duplicate normalized email

- GIVEN an account exists for the normalized email
- WHEN the client registers any casing variant of that email
- THEN the API rejects the duplicate with HTTP status 409

### Requirement: Authenticate with OAuth2 Credentials

The system MUST expose OAuth2 form login at `POST /auth/login`, with email as
`username`. Valid active-account credentials MUST return a bearer token.
Invalid credentials MUST return Spanish HTTP 401; valid inactive-account
credentials MUST return distinct Spanish HTTP 403.

#### Scenario: Login active account

- GIVEN an active account and matching email and password
- WHEN OAuth2 login uses any email casing
- THEN the API returns a bearer access token

#### Scenario: Reject invalid credentials

- GIVEN an unknown email or incorrect password
- WHEN the client attempts login
- THEN the API responds with HTTP status 401
- AND the error describes invalid credentials in Spanish

#### Scenario: Reject inactive account

- GIVEN an inactive account and matching credentials
- WHEN the client attempts login
- THEN the API responds with HTTP status 403
- AND the error describes inactivity in Spanish

### Requirement: Issue Bounded Access Tokens

An access token MUST identify the user, expire after 30 minutes, and MUST NOT
contain credentials. Invalid or expired tokens MUST receive Spanish HTTP 401.

#### Scenario: Issue token with bounded lifetime

- GIVEN a successful login
- WHEN the token is inspected
- THEN it identifies that user and expires 30 minutes after issuance
- AND it contains no password or password hash

#### Scenario: Reject unusable token

- GIVEN an invalid or expired bearer token
- WHEN it is used for authenticated access
- THEN the API responds with HTTP status 401
- AND the error is in Spanish

### Requirement: Return the Authenticated Profile

`GET /auth/me` MUST return only the safe profile of the active user identified
by a valid bearer token.

#### Scenario: Read own profile

- GIVEN an active user with a valid access token
- WHEN the user requests `/auth/me`
- THEN the API returns that user's safe profile

### Requirement: Preserve User Read Access and Move Creation

`GET /users` and `GET /users/{user_id}` MUST remain public. `POST /users` MUST
NOT create users; registration MUST use `/auth/register`.

#### Scenario: Use public user routes

- GIVEN an unauthenticated client
- WHEN it requests either user read endpoint
- THEN authentication is not required

#### Scenario: Reject former creation route

- GIVEN valid registration data
- WHEN the client sends `POST /users`
- THEN no user-creation operation is available at that route

### Requirement: Use Client-Side Logout

The system MUST NOT expose server-side logout or revocation. A client MAY end
its local session by discarding its access token.

#### Scenario: End local session

- GIVEN a client holds an access token
- WHEN the client discards the token
- THEN the client retains no credential for subsequent authenticated requests
