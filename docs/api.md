# API Reference

## Overview

MedLens exposes a REST API built with FastAPI. This document describes the endpoints that are currently implemented.

All endpoints return JSON.

---

## Base URL

```text
http://localhost:8000
```

This is the local development URL when running the backend directly (`uvicorn app.main:app --reload`) or through Docker Compose (`docker compose up --build` from `infra/`).

---

## Authentication

Authentication uses JSON Web Tokens (JWT).

A token is obtained by calling `POST /auth/login` with valid credentials. The token is a short-lived access token containing the user's id in the `sub` claim, signed with the algorithm and secret configured in the backend settings, and expiring after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (30 minutes by default).

Protected endpoints require the token to be sent as a Bearer token in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

If the header is missing, the token is malformed or expired, or the token references a user that no longer exists, the request is rejected with `401 Unauthorized`.

---

## Endpoints

### GET /

Description

Root endpoint. Confirms the API is running.

Request

No parameters or body.

Response

```json
{
  "message": "Welcome to MedLens API"
}
```

---

### GET /health

Description

Reports API and database connectivity status.

Request

No parameters or body.

Response

```json
{
  "status": "ok",
  "database": "connected"
}
```

If the database connection fails, the response body reflects the failure instead:

```json
{
  "status": "error",
  "database": "disconnected",
  "detail": "<error message>"
}
```

Note: the endpoint currently returns HTTP `200` in both cases. Callers should check the `status` field in the body rather than the HTTP status code.

---

### POST /auth/register

Purpose

Creates a new user account.

Request body

```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "name": "Jane Doe"
}
```

`name` is optional.

Validation rules

- `email` must be a valid email address.
- `password` must be at least 8 characters long.
- `email` must not already belong to a registered user.

Success response

`201 Created`

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Jane Doe",
  "created_at": "2026-07-03T19:13:05.755361Z"
}
```

The stored password hash is never included in the response.

Possible error responses

- `409 Conflict` — the email is already registered.
- `422 Unprocessable Entity` — invalid email format, password shorter than 8 characters, or missing required fields.

---

### POST /auth/login

Purpose

Authenticates an existing user and issues an access token.

Request body

```json
{
  "email": "user@example.com",
  "password": "securepassword"
}
```

Success response

`200 OK`

JWT response format

```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

The decoded token payload contains:

```json
{
  "sub": "1",
  "exp": 1783108877
}
```

`sub` is the authenticated user's id (as a string); `exp` is the expiration time as a Unix timestamp.

Possible error responses

- `401 Unauthorized` — the email is not registered, or the password is incorrect. The same error message is returned in both cases so that the response does not reveal whether an email is registered.
- `422 Unprocessable Entity` — missing or malformed request body.

---

### GET /users/me

Purpose

Returns the profile of the currently authenticated user.

Authentication requirements

Requires a valid Bearer token in the `Authorization` header, as described above.

Success response

`200 OK`

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Jane Doe",
  "created_at": "2026-07-03T19:13:05.755361Z"
}
```

401 responses

- Missing `Authorization` header — `{"detail": "Not authenticated"}`
- Invalid, malformed, or expired token — `{"detail": "Could not validate credentials"}`
- Token is well-formed and correctly signed but references a user id that no longer exists — `{"detail": "Could not validate credentials"}`

---

### POST /medications

Purpose

Creates a medication entry in the authenticated user's medication list.

Request body

```json
{
  "medication_name": "Lisinopril",
  "dose": "10 mg",
  "route": "oral",
  "frequency": "once daily",
  "status": "active",
  "source": "patient_reported",
  "notes": "Taken with breakfast"
}
```

`notes` is optional.

Validation rules

- `medication_name`, `dose`, `route`, `frequency`, `status`, and `source` are required and must not be empty.
- `notes` may be omitted or set to `null`.

Success response

`201 Created`

```json
{
  "id": 1,
  "user_id": 1,
  "medication_name": "Lisinopril",
  "dose": "10 mg",
  "route": "oral",
  "frequency": "once daily",
  "status": "active",
  "source": "patient_reported",
  "notes": "Taken with breakfast",
  "created_at": "2026-07-12T19:59:14.696845Z",
  "updated_at": null
}
```

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `422 Unprocessable Entity`: a required field is missing or empty.

---

### POST /medications/import

Purpose

Imports medications into the authenticated user's medication list from an uploaded CSV file.

Accepted file type

`.csv` file extension or `text/csv` content type. Any other file type is rejected.

Expected headers

```text
medication_name
dose
route
frequency
status
source
notes
```

`medication_name`, `dose`, `route`, `frequency`, `status`, and `source` are required headers. `notes` is optional. Header names are matched case-insensitively and with surrounding whitespace trimmed, so `Medication_Name` and ` medication_name ` are both accepted. Extra columns beyond the ones listed above are ignored.

Row behavior

- Surrounding whitespace is trimmed from every header and every cell value.
- A row where every recognized column is empty is treated as a blank row and ignored. Blank rows are counted separately in the response and do not cause an error.
- An empty `notes` cell is stored as `null`, matching the other creation endpoints.
- Each nonblank row is validated using the same rules as `POST /medications`.

Import is atomic. Every row is validated before any medication is created. If any nonblank row fails validation, no medications are created and the response reports every invalid row.

Example CSV content

```csv
medication_name,dose,route,frequency,status,source,notes
Lisinopril,10 mg,oral,once daily,active,patient_reported,Taken with breakfast
Metformin,500 mg,oral,twice daily,active,patient_reported,
```

Success response

`201 Created`

```json
{
  "rows_processed": 2,
  "medications_created": 2,
  "blank_rows_ignored": 0
}
```

`rows_processed` counts every nonheader row read from the file, including blank rows. `medications_created` counts the medications actually created. `blank_rows_ignored` counts rows skipped because every recognized column was empty.

Validation error response

`422 Unprocessable Entity`

Row numbers follow spreadsheet convention: the header is row 1, so the first data row is row 2.

```json
{
  "detail": {
    "message": "CSV import failed validation. No medications were created.",
    "row_errors": [
      {
        "row": 3,
        "errors": [
          {
            "field": "dose",
            "message": "String should have at least 1 character"
          }
        ]
      }
    ]
  }
}
```

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `422 Unprocessable Entity`: the file is not a CSV, the file is empty or has no header row, the header row is missing a required column, or one or more rows fail validation. When one or more rows fail validation, no medications are created.

---

### GET /medications

Purpose

Returns all medications belonging to the authenticated user.

Request

No parameters or body.

Response

`200 OK`

```json
[
  {
    "id": 1,
    "user_id": 1,
    "medication_name": "Lisinopril",
    "dose": "10 mg",
    "route": "oral",
    "frequency": "once daily",
    "status": "active",
    "source": "patient_reported",
    "notes": "Taken with breakfast",
    "created_at": "2026-07-12T19:59:14.696845Z",
    "updated_at": null
  }
]
```

Only medications belonging to the current user are returned.

---

### GET /medications/{medication_id}

Purpose

Returns a single medication belonging to the authenticated user.

Authentication requirements

Requires a valid Bearer token in the `Authorization` header, as described above.

Success response

`200 OK`

```json
{
  "id": 1,
  "user_id": 1,
  "medication_name": "Lisinopril",
  "dose": "10 mg",
  "route": "oral",
  "frequency": "once daily",
  "status": "active",
  "source": "patient_reported",
  "notes": "Taken with breakfast",
  "created_at": "2026-07-12T19:59:14.696845Z",
  "updated_at": null
}
```

404 responses

Returned if `medication_id` does not exist or belongs to a different user. The same response is used in both cases so that a caller cannot distinguish a nonexistent medication from one owned by someone else.

```json
{
  "detail": "Medication not found"
}
```

---

### PATCH /medications/{medication_id}

Purpose

Partially updates a medication belonging to the authenticated user. Only the fields included in the request body are changed.

Request body

```json
{
  "dose": "20 mg",
  "status": "discontinued"
}
```

Any subset of `medication_name`, `dose`, `route`, `frequency`, `status`, `source`, and `notes` may be included.

Validation rules

- Any included field other than `notes` must not be empty.
- `notes` may be set to `null`.
- Fields left out of the request body are unchanged.

Success response

`200 OK`

```json
{
  "id": 1,
  "user_id": 1,
  "medication_name": "Lisinopril",
  "dose": "20 mg",
  "route": "oral",
  "frequency": "once daily",
  "status": "discontinued",
  "source": "patient_reported",
  "notes": "Taken with breakfast",
  "created_at": "2026-07-12T19:59:14.696845Z",
  "updated_at": "2026-07-12T19:59:15.112249Z"
}
```

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: the medication does not exist or does not belong to the current user.
- `422 Unprocessable Entity`: an included field is empty.

---

### DELETE /medications/{medication_id}

Purpose

Deletes a medication belonging to the authenticated user.

Success response

`204 No Content`

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: the medication does not exist or does not belong to the current user.

---

## Error Responses

### 400 Bad Request

Reserved for malformed requests. No endpoint currently returns this status directly — request body validation failures surface as `422` instead (see below).

### 401 Unauthorized

Returned for failed login attempts and for any request to a protected endpoint that lacks a valid, current access token.

```json
{
  "detail": "Incorrect email or password"
}
```

```json
{
  "detail": "Could not validate credentials"
}
```

### 404 Not Found

Returned when a requested resource does not exist, or exists but does not belong to the authenticated user. Both cases return the same response so that a caller cannot tell the two apart. Used by the `/medications/{medication_id}` endpoints.

```json
{
  "detail": "Medication not found"
}
```

### 409 Conflict

Returned by `POST /auth/register` when the given email is already registered.

```json
{
  "detail": "A user with this email is already registered"
}
```

### 422 Unprocessable Entity

Returned when the request body fails validation (invalid email format, password too short, missing required fields, or malformed JSON).

```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "email"],
      "msg": "Field required"
    }
  ]
}
```

---

## Notes

This API currently supports authentication, application infrastructure, clinical document management, and user-owned medication list management (`/`, `/health`, `/auth/register`, `/auth/login`, `/users/me`, `/medications`). AI-based medication extraction and reconciliation endpoints are not yet implemented and will be introduced in future sprints.
