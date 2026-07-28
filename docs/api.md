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

### POST /patients

Purpose

Creates a patient record owned by the authenticated user (provider).

Request body

```json
{
  "first_name": "Jane",
  "last_name": "Doe",
  "date_of_birth": "1980-05-14",
  "external_mrn": "MRN-001",
  "notes": "Prefers morning appointments"
}
```

`external_mrn` and `notes` are optional.

Validation rules

- `first_name`, `last_name`, and `date_of_birth` are required.
- `first_name` and `last_name` must not be empty.
- `date_of_birth` must be a valid date.

Success response

`201 Created`

```json
{
  "id": 1,
  "user_id": 1,
  "first_name": "Jane",
  "last_name": "Doe",
  "date_of_birth": "1980-05-14",
  "external_mrn": "MRN-001",
  "status": "active",
  "notes": "Prefers morning appointments",
  "created_at": "2026-07-28T19:59:14.696845Z",
  "updated_at": null
}
```

`status` always starts as `active` and cannot be set at creation time.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `422 Unprocessable Entity`: a required field is missing, empty, or `date_of_birth` is not a valid date.

---

### GET /patients

Purpose

Returns every non-archived patient owned by the authenticated user.

Request

No parameters or body.

Response

`200 OK`

```json
[
  {
    "id": 1,
    "user_id": 1,
    "first_name": "Jane",
    "last_name": "Doe",
    "date_of_birth": "1980-05-14",
    "external_mrn": "MRN-001",
    "status": "active",
    "notes": "Prefers morning appointments",
    "created_at": "2026-07-28T19:59:14.696845Z",
    "updated_at": null
  }
]
```

Only patients belonging to the current user are returned, and archived patients (see `DELETE /patients/{patient_id}` below) are excluded. There is no way to list archived patients through this endpoint yet.

---

### GET /patients/{patient_id}

Purpose

Returns a single patient belonging to the authenticated user.

Authentication requirements

Requires a valid Bearer token in the `Authorization` header, as described above.

Success response

`200 OK`

```json
{
  "id": 1,
  "user_id": 1,
  "first_name": "Jane",
  "last_name": "Doe",
  "date_of_birth": "1980-05-14",
  "external_mrn": "MRN-001",
  "status": "active",
  "notes": "Prefers morning appointments",
  "created_at": "2026-07-28T19:59:14.696845Z",
  "updated_at": null
}
```

Unlike `GET /patients`, this endpoint returns a patient regardless of `status`, so an archived patient's own record is still reachable directly.

404 responses

Returned if `patient_id` does not exist or belongs to a different user. The same response is used in both cases so that a caller cannot distinguish a nonexistent patient from one owned by someone else.

```json
{
  "detail": "Patient not found"
}
```

---

### PATCH /patients/{patient_id}

Purpose

Partially updates a patient belonging to the authenticated user. Only the fields included in the request body are changed.

Request body

```json
{
  "last_name": "Smith",
  "notes": "Moved to a new address"
}
```

Any subset of `first_name`, `last_name`, `date_of_birth`, `external_mrn`, and `notes` may be included.

Validation rules

- `first_name` and `last_name`, if included, must not be empty.
- `date_of_birth`, if included, must be a valid date.
- Fields left out of the request body are unchanged.
- `status` cannot be changed through this endpoint. It is silently ignored if present in the request body; use `DELETE /patients/{patient_id}` to archive a patient instead.

Success response

`200 OK`

```json
{
  "id": 1,
  "user_id": 1,
  "first_name": "Jane",
  "last_name": "Smith",
  "date_of_birth": "1980-05-14",
  "external_mrn": "MRN-001",
  "status": "active",
  "notes": "Moved to a new address",
  "created_at": "2026-07-28T19:59:14.696845Z",
  "updated_at": "2026-07-28T20:04:02.112249Z"
}
```

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: the patient does not exist or does not belong to the current user.
- `422 Unprocessable Entity`: an included field is empty or invalid.

---

### DELETE /patients/{patient_id}

Purpose

Archives a patient belonging to the authenticated user. This is a soft delete: the patient row is never removed, only its `status` is set to `archived`. An archived patient is excluded from `GET /patients` but remains reachable through `GET /patients/{patient_id}` and `PATCH /patients/{patient_id}`. There is currently no way to reverse an archive back to `active`.

Success response

`204 No Content`

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: the patient does not exist or does not belong to the current user.

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

### POST /ai/summarize

Purpose

Summarizes one or more of the authenticated user's clinical documents using the configured AI provider, and persists the result as a completed Analysis. See `docs/ai.md` for the provider architecture and `docs/data-model.md` for what is stored.

Request body

```json
{
  "clinical_document_ids": [1, 2]
}
```

Validation rules

- `clinical_document_ids` is required and must contain at least one id.

Success response

`201 Created`

```json
{
  "analysis_id": 7,
  "provider": "gemini",
  "model": "gemini-2.0-flash",
  "medications": [
    {
      "name": "Lisinopril",
      "dosage": "10 mg",
      "route": "oral",
      "frequency": "once daily",
      "status": "active",
      "notes": null
    }
  ],
  "possible_inconsistencies": [],
  "summary": "..."
}
```

`medications`, `possible_inconsistencies`, and `summary` are the provider's response, parsed as JSON and validated against a Pydantic schema. `analysis_id` identifies the Analysis this request created, whose fields, medication mentions, and inconsistencies are persisted before the response is returned. No discrepancy detection or reconciliation is performed on it. See `docs/ai.md` for the full response schema.

If a requested document does not exist or is not owned by the caller, no Analysis is created at all. If the AI provider or persistence fails after the Analysis is created, it is marked `failed` with a sanitized error message rather than left in an incomplete state. See Error Responses below.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: a requested document does not exist or does not belong to the current user.
- `422 Unprocessable Entity`: `clinical_document_ids` is missing or empty.
- `503 Service Unavailable`: the AI provider could not produce a usable response, including a missing API key, a request failure, a timeout, malformed JSON, or a response that fails schema validation.

---

### GET /ai/analyses

Purpose

Returns a page of the authenticated user's own analyses, most recently created first, for use as a "recent analyses" list. Read-only; no query parameter can widen the result beyond the caller's own analyses.

Authentication requirements

Requires a valid Bearer token in the `Authorization` header, as described above.

Query parameters

- `limit` (optional, integer, default `10`, minimum `1`, maximum `50`): the maximum number of analyses to return.

Success response

`200 OK`

```json
[
  {
    "id": 7,
    "status": "completed",
    "created_at": "2026-07-12T19:59:14.500000Z",
    "completed_at": "2026-07-12T19:59:16.112249Z",
    "error_message": null,
    "summary": "Reconciliation completed across 2 clinical document(s) with 1 finding(s): 0 high, 1 medium, 0 low severity.",
    "document_count": 2,
    "total_findings": 1,
    "high_severity_findings": 0,
    "medium_severity_findings": 1,
    "low_severity_findings": 0,
    "provider": "gemini",
    "model_name": "gemini-2.0-flash"
  }
]
```

An empty list is returned if the user has no analyses yet; this is a normal, successful response, not an error. Ordering is by `id` descending, not `created_at`, since rows created together can share an identical `created_at` (Postgres's `now()` is constant within a transaction). Unlike `GET /ai/analyses/{analysis_id}`, list rows never include `medication_mentions` or `possible_inconsistencies`; fetch the detail endpoint for that.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `422 Unprocessable Entity`: `limit` is outside the `1`-`50` range.

---

### GET /ai/analyses/{analysis_id}

Purpose

Returns the metadata and persisted results of one of the authenticated user's analyses. Read-only: it does not create, rerun, or modify an analysis. See `docs/data-model.md` for the underlying `Analysis`, `AnalysisMedicationMention`, and `AnalysisInconsistency` models.

Authentication requirements

Requires a valid Bearer token in the `Authorization` header, as described above.

Success response

`200 OK`

```json
{
  "id": 7,
  "status": "completed",
  "provider": "gemini",
  "model_name": "gemini-2.0-flash",
  "summary": "...",
  "started_at": "2026-07-12T19:59:14.696845Z",
  "completed_at": "2026-07-12T19:59:16.112249Z",
  "error_message": null,
  "created_at": "2026-07-12T19:59:14.500000Z",
  "updated_at": "2026-07-12T19:59:16.112249Z",
  "medication_mentions": [
    {
      "id": 3,
      "medication_name": "Lisinopril",
      "dosage": "10 mg",
      "route": "oral",
      "frequency": "once daily",
      "status": "active",
      "notes": null
    }
  ],
  "possible_inconsistencies": [
    {
      "id": 2,
      "description": "Lisinopril dose differs between the admission note and the discharge summary."
    }
  ]
}
```

`medication_mentions` and `possible_inconsistencies` are always returned, sorted by ascending `id`, even for analyses that have none (an empty list) or that failed before persisting any results (both lists empty, `summary`, `provider`, and `model_name` are `null`).

`error_message` is `null` unless `status` is `"failed"`, in which case it holds the same sanitized message returned by `POST /ai/summarize` at failure time (see that endpoint's `503` response above). It never contains a stack trace, a provider exception, `ValidationError` details, raw AI output, or a raw SQL error; only the sanitized message already stored on the Analysis is exposed.

404 responses

Returned if `analysis_id` does not exist or belongs to a different user. The same response is used in both cases so that a caller cannot distinguish a nonexistent analysis from one owned by someone else.

```json
{
  "detail": "Analysis not found"
}
```

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: the analysis does not exist or does not belong to the current user.

---

### DELETE /ai/analyses/{analysis_id}

Purpose

Permanently deletes one of the authenticated user's analyses, along with its persisted `AnalysisMedicationMention`, `AnalysisInconsistency`, and `MedicationDiscrepancy` rows. Does not delete clinical documents, medications, or any other reusable resource; only data scoped to this analysis is removed.

Authentication requirements

Requires a valid Bearer token in the `Authorization` header, as described above.

Success response

`204 No Content`

No response body. After a successful delete, `GET /ai/analyses/{analysis_id}` for the same id returns `404`.

404 responses

Returned if `analysis_id` does not exist or belongs to a different user, using the same response as `GET /ai/analyses/{analysis_id}` so a caller cannot distinguish a nonexistent analysis from one owned by someone else.

```json
{
  "detail": "Analysis not found"
}
```

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: the analysis does not exist or does not belong to the current user.

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

Returned when a requested resource does not exist, or exists but does not belong to the authenticated user. Both cases return the same response so that a caller cannot tell the two apart. Used by the `/medications/{medication_id}` and `/ai/analyses/{analysis_id}` endpoints.

```json
{
  "detail": "Medication not found"
}
```

```json
{
  "detail": "Analysis not found"
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

### 503 Service Unavailable

Returned by `POST /ai/summarize` when the configured AI provider cannot produce a response, including a missing API key, a request failure, a timeout, or an invalid response.

```json
{
  "detail": "Gemini API key is not configured"
}
```

---

## Notes

This API currently supports authentication, application infrastructure, clinical document management, user-owned medication list management, AI-generated document summaries persisted as analyses, and listing, retrieval, and deletion of a user's own analyses (`/`, `/health`, `/auth/register`, `/auth/login`, `/users/me`, `/medications`, `/ai/summarize`, `/ai/analyses`, `/ai/analyses/{analysis_id}`). Medication reconciliation exists as internal backend logic but has no API endpoint yet; discrepancy detection results are not yet exposed through this API and will be introduced in a future sprint.
