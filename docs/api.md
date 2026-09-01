# API Reference

## Overview

MedLens exposes a REST API built with FastAPI. This document describes the endpoints that are currently implemented.

All endpoints return JSON (`Content-Type: application/json`), except `GET /patients/{patient_id}/clinical-documents/{document_id}/download`, which streams the original uploaded file back with its own stored `Content-Type` (see File Uploads below). Every JSON request body is also `application/json`, except the three `upload-txt`/`upload-pdf`/`upload-csv` endpoints, which take `multipart/form-data`.

Error responses always have a JSON body with a `detail` key - either a string (most errors) or a structured value (request validation failures, and the CSV import endpoint's row-level errors). See Error Responses below for the exact shape returned by each status code.

This document is a companion to, not a replacement for, the OpenAPI schema FastAPI generates automatically from the code itself - see OpenAPI / Interactive Docs at the end of this document.

---

## Base URL

Every endpoint in this document is documented by its path alone (e.g. `POST /auth/login`) - which base URL that path is relative to depends on how you're reaching the backend:

```text
http://localhost:8000       # direct access - running the backend with `uvicorn app.main:app --reload`,
                             # or Docker Compose's backend container (127.0.0.1 only - see docs/deployment.md)
http://<app-origin>/api      # through the app itself - the frontend's own origin, prefixed
                             # with /api, e.g. https://medlenshealth.com/api/auth/login. This is what the
                             # browser actually uses; nginx reverse-proxies /api/* to the backend and
                             # strips the prefix, so POST /api/auth/login here means POST /auth/login below.
```

The browser never uses the first form - only tools talking to the backend directly (`curl`, Postman, the API docs above) do, and even then only from the same host the backend is running on, or over the Docker network - see `docs/deployment.md`'s Reverse Proxy section for why.

---

## Authentication

Authentication uses JSON Web Tokens (JWT).

A token is obtained by calling `POST /auth/login` with valid credentials. The token is a short-lived access token containing the user's id in the `sub` claim, signed with the algorithm and secret configured in the backend settings, and expiring after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (30 minutes by default).

Protected endpoints require the token to be sent as a Bearer token in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

If the header is missing, the token is malformed or expired, or the token references a user that no longer exists, the request is rejected with `401 Unauthorized`.

There is no refresh token and no logout endpoint: a token is simply valid until it expires, and a client discarding it is the only "logout" that exists today.

---

## Authentication Flow

```text
POST /auth/register          Create an account (email, password, username)
        │
        ▼
POST /auth/login              Exchange email + password for a JWT
        │
        ▼
   Receive JWT                 { "access_token": "<jwt>", "token_type": "bearer" }
        │
        ▼
Authorization: Bearer <jwt>   Attach to every subsequent request
        │
        ▼
Access protected endpoints    GET /users/me, /patients, /patients/{id}/medications, ...
```

Registering does **not** log the new account in - `POST /auth/register` returns the created user's profile (`UserResponse`), not a token. A client must call `POST /auth/login` immediately afterward to obtain one, the same as any other login. Every endpoint except `GET /`, `GET /health`, `POST /auth/register`, and `POST /auth/login` requires the header above; see each endpoint's own "Authentication requirements" for confirmation.

---

## Schemas

Every request and response body below is shown as a full worked JSON example under its endpoint - this section only covers the shapes that are *shared* across more than one endpoint, so their shape is documented once rather than repeated. For the exact field types, constraints (min length, nullability), and full enum definitions straight from the Pydantic models themselves, see `GET /docs` or `GET /openapi.json` (OpenAPI / Interactive Docs, below) - those are generated directly from the code and can never drift from it the way hand-written field tables can.

Reused/nested response shapes:

- **`PatientSummaryResponse`** (`id`, `first_name`, `last_name`) - a minimal patient citation, used wherever a resource needs to identify its owning patient without embedding the full `PatientResponse`. Appears in `GET /analyses/recent`.
- **`ClinicalDocumentSummaryResponse`** (`id`, `title`, `document_type`) - a minimal document citation with no `raw_text`, used when citing a document as supporting evidence. Appears nested inside `medication_mention.clinical_document` in `GET /patients/{patient_id}/analyses/{analysis_id}`.
- **`MedicationResponse`** - the same full medication shape returned by `GET /patients/{patient_id}/medications/{medication_id}` is also embedded directly (not summarized) in a resolved discrepancy's `medication` field, since a provider reviewing a finding needs the complete row, not a citation.

Enums used across more than one field (full definitions in `app/schemas/`):

| Enum | Values |
|---|---|
| `AnalysisStatus` | `pending`, `processing`, `completed`, `failed` |
| `DiscrepancyType` | `missing_from_medication_list`, `discontinued_status_conflict`, `dose_conflict`, `route_conflict`, `frequency_conflict`, `status_conflict`, `unsupported_medication_list_entry` |
| `DiscrepancySeverity` | `low`, `medium`, `high` |
| `ResolutionStatus` | `open`, `reviewed`, `resolved`, `dismissed` |
| `ResolutionAction` | `add_medication`, `update_medication`, `dismiss` |

All five are serialized as plain strings in JSON (Pydantic `str` enums) - a client never needs to decode an integer or otherwise-encoded value.

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

Reports application status, database connectivity, and the deployment configuration already loaded into memory (version, environment, storage backend, AI provider/model) - a single place to check "what is this instance actually running as" without SSHing in. Deliberately lightweight: the only I/O it performs is one `SELECT 1` against the database this process already holds a connection pool for. It never contacts Gemini or Hugging Face, never makes an S3 request, and never performs any other network call - `storage`/`ai` below are read directly from configuration already in memory (and, for `ai.provider`, a plain class attribute), not by constructing a real storage backend or AI provider client.

Request

No parameters or body.

Response

`200 OK`

```json
{
  "status": "ok",
  "version": "1.0.0",
  "environment": "production",
  "database": {
    "status": "connected"
  },
  "storage": {
    "backend": "s3"
  },
  "ai": {
    "provider": "gemini",
    "model": "gemini-2.5-flash"
  },
  "timestamp": "2026-08-04T02:15:30Z"
}
```

If the database connection fails, `status` and `database` reflect the failure instead - every other field is still populated exactly the same way, since none of them ever depended on the database to begin with, and they remain useful (arguably more so) while diagnosing this exact failure:

```json
{
  "status": "error",
  "version": "1.0.0",
  "environment": "production",
  "database": {
    "status": "disconnected",
    "detail": "<error message>"
  },
  "storage": {
    "backend": "s3"
  },
  "ai": {
    "provider": "gemini",
    "model": "gemini-2.5-flash"
  },
  "timestamp": "2026-08-04T02:15:30Z"
}
```

`503 Service Unavailable` is returned in this case - unlike an outdated assumption once written here, this endpoint does **not** always return `200`; callers can rely on the HTTP status code directly (a `503` should still be treated as a real signal by anything that scripts against this endpoint, e.g. a load balancer or orchestrator health check - see `docs/deployment.md`), and may additionally check the `status` field in the body for the same information.

Field notes:

- `version` - `Settings.app_version` (`APP_VERSION` environment variable, defaults to `"1.0.0"`). A plain configured string, not derived from git or the Docker image tag.
- `environment` - `Settings.app_env` (`APP_ENV`), the same value that gates CORS behavior elsewhere (see `POST /auth/register` and friends).
- `storage.backend` - `Settings.storage_backend` (`STORAGE_BACKEND`), `"local"` or `"s3"` - see `docs/deployment.md`'s File Storage (S3) section. Never `"s3"` because a request to S3 actually succeeded; it's the *configured* backend, reported without contacting it.
- `ai.provider` / `ai.model` - reflect `Settings.ai_provider` (`AI_PROVIDER`, `"gemini"` or `"openbiollm"`): `"gemini"` / `Settings.gemini_model`, or `"openbiollm"` / `Settings.openbiollm_model`. Reporting either requires no credential and makes no request to Gemini or Hugging Face - unlike using AI features themselves, which fail with a `503` and a different message when the active provider's credential is missing (see that endpoint above).
- `timestamp` - UTC, formatted like `2026-08-04T02:15:30Z`.

---

### POST /auth/register

Purpose

Creates a new user account.

Request body

```json
{
  "email": "user@example.com",
  "password": "securepassword",
  "username": "jane_doe",
  "name": "Jane Doe"
}
```

`name` is optional. `username` is required - every account created from this point forward has one; see `docs/data-model.md`'s `User` entity for why the underlying column is nullable despite that.

Validation rules

- `email` must be a valid email address.
- `password` must be at least 8 characters long.
- `email` must not already belong to a registered user.
- `username` must be 3–30 characters long, containing only letters, numbers, underscores, and periods (`a-z`, `A-Z`, `0-9`, `_`, `.`).
- `username` must not already belong to a registered user - checked **case-insensitively**: `jdoe` and `JDoe` are treated as the same username for this check, even though the value is stored and returned exactly as submitted.

Success response

`201 Created`

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Jane Doe",
  "username": "jane_doe",
  "created_at": "2026-07-03T19:13:05.755361Z"
}
```

The stored password hash is never included in the response.

Possible error responses

- `409 Conflict` - the email is already registered (`"A user with this email is already registered"`), or the username is already taken, case-insensitively (`"This username is already taken"`).
- `422 Unprocessable Entity` - invalid email format, password shorter than 8 characters, `username` missing or failing its format rules above, or another required field missing.

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

- `401 Unauthorized` - the email is not registered, or the password is incorrect. The same error message is returned in both cases so that the response does not reveal whether an email is registered.
- `422 Unprocessable Entity` - missing or malformed request body.

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
  "username": "jane_doe",
  "created_at": "2026-07-03T19:13:05.755361Z"
}
```

`username` is `null` for any account that predates usernames and hasn't set one since - see `docs/data-model.md`.

401 responses

- Missing `Authorization` header - `{"detail": "Not authenticated"}`
- Invalid, malformed, or expired token - `{"detail": "Could not validate credentials"}`
- Token is well-formed and correctly signed but references a user id that no longer exists - `{"detail": "Could not validate credentials"}`

---

### PATCH /users/me

Purpose

Partially updates the authenticated user's own profile. Only the fields included in the request body are changed; this is a profile-editing endpoint, not a credential change - there is no way to change a password here, and authentication always continues to use email/password regardless of whether a username is set.

Authentication requirements

Requires a valid Bearer token in the `Authorization` header, as described above.

Request body

```json
{
  "username": "new_username"
}
```

Any subset of `email`, `name`, and `username` may be included. Extra/unrecognized fields are rejected outright rather than silently ignored.

Validation rules

- `email`, if included, must be a valid email address, and must not already belong to a different user.
- `username`, if included:
  - `null` clears it (an account can always go back to having no username).
  - A non-null value must pass the same 3–30 character, `a-z`/`A-Z`/`0-9`/`_`/`.`-only rules `POST /auth/register` enforces.
  - A non-null value must not already belong to a *different* user, checked case-insensitively - re-submitting your own current username with different casing (e.g. `jdoe` → `JDoe`) is allowed, the same way re-submitting your own current email is.
- Fields left out of the request body are unchanged.

Success response

`200 OK` - the same shape as `GET /users/me`, reflecting the update:

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Jane Doe",
  "username": "new_username",
  "created_at": "2026-07-03T19:13:05.755361Z"
}
```

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `409 Conflict`: the given `email` already belongs to another user (`"A user with this email is already registered"`), or the given `username` already belongs to another user, case-insensitively (`"This username is already taken"`).
- `422 Unprocessable Entity`: `email` is not a valid email address, `username` fails its format rules, or the request body contains a field this endpoint doesn't recognize.

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

### POST /patients/{patient_id}/medications

Purpose

Creates a medication entry in the given patient's medication list. Medications are owned by a `Patient`, not directly by the authenticated user - see `docs/data-model.md`.

Authorization

Every route in this section resolves `patient_id` through the same check: the patient must exist and belong to the authenticated user (`Patient.user_id == current_user.id`), via a shared dependency (`get_owned_patient`). This applies uniformly whether the patient is active or archived - an archived patient's medications remain fully manageable through these endpoints, only `GET /patients` (the active patient list) excludes them.

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
  "patient_id": 1,
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
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user - `{"detail": "Patient not found"}`.
- `422 Unprocessable Entity`: a required field is missing or empty.

---

### POST /patients/{patient_id}/medications/import

Purpose

Imports medications into the given patient's medication list from an uploaded CSV file.

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
- Each nonblank row is validated using the same rules as `POST /patients/{patient_id}/medications`.

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
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user.
- `422 Unprocessable Entity`: the file is not a CSV, the file is empty or has no header row, the header row is missing a required column, or one or more rows fail validation. When one or more rows fail validation, no medications are created.

---

### GET /patients/{patient_id}/medications

Purpose

Returns all medications belonging to the given patient.

Request

No parameters or body beyond `patient_id` in the path.

Response

`200 OK`

```json
[
  {
    "id": 1,
    "patient_id": 1,
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

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user.

---

### GET /patients/{patient_id}/medications/{medication_id}

Purpose

Returns a single medication belonging to the given patient.

Authentication requirements

Requires a valid Bearer token in the `Authorization` header, as described above.

Success response

`200 OK`

```json
{
  "id": 1,
  "patient_id": 1,
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

Returned if `patient_id` does not exist or does not belong to the current user, or if `medication_id` does not exist or belongs to a *different* patient - including a different patient owned by the same user. The same response is used in every case so that a caller cannot distinguish a nonexistent medication from one it isn't allowed to see.

```json
{
  "detail": "Patient not found"
}
```

```json
{
  "detail": "Medication not found"
}
```

---

### PATCH /patients/{patient_id}/medications/{medication_id}

Purpose

Partially updates a medication belonging to the given patient. Only the fields included in the request body are changed.

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
  "patient_id": 1,
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
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user, or the medication does not exist or belongs to a different patient.
- `422 Unprocessable Entity`: an included field is empty.

---

### DELETE /patients/{patient_id}/medications/{medication_id}

Purpose

Deletes a medication belonging to the given patient. Unlike archiving a patient, this is a real, permanent delete - there is no soft-delete for individual medications.

Success response

`204 No Content`

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user, or the medication does not exist or belongs to a different patient.

---

### POST /patients/{patient_id}/clinical-documents

Purpose

Creates a clinical document from pasted text, belonging to the given patient. Clinical documents are owned by a `Patient`, not directly by the authenticated user - see `docs/data-model.md`.

Authorization

Every route in this section resolves `patient_id` through the same shared `get_owned_patient` dependency used by the medication routes: the patient must exist and belong to the authenticated user. This applies uniformly whether the patient is active or archived - an archived patient's clinical documents remain fully manageable through these endpoints, only `GET /patients` (the active patient list) excludes them.

Request body

```json
{
  "document_type": "visit_note",
  "title": "Initial Visit",
  "raw_text": "Patient presents with hypertension."
}
```

Validation rules

- `document_type`, `title`, and `raw_text` are required and must not be empty.

Success response

`201 Created`

```json
{
  "id": 1,
  "patient_id": 1,
  "document_type": "visit_note",
  "title": "Initial Visit",
  "raw_text": "Patient presents with hypertension.",
  "file_name": null,
  "file_type": "manual_entry",
  "content_type": null,
  "file_size_bytes": null,
  "created_at": "2026-07-12T19:59:14.696845Z",
  "updated_at": null,
  "analysis_count": 0
}
```

`analysis_count` is `len(document.analyses)` - how many analyses this document has been included in via `POST /patients/{patient_id}/analyses`'s `clinical_document_ids` (a computed property on the model, not a stored column; the same pattern as `AnalysisSummaryResponse.document_count`). A brand-new document always starts at `0`.

`content_type` and `file_size_bytes` are `null` for a document created this way - pasted text has no original file, so there is nothing to store in S3/local storage and nothing to report a size or content type for. See `upload-txt`/`upload-pdf`/`upload-csv` below for when they're populated, and `GET .../{document_id}/download` for retrieving the file itself. There is no `storage_key` field in this response at all - it identifies the object in whichever storage backend is configured (a local path or an S3 key), and is never exposed over the API; see `docs/architecture.md`.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user - `{"detail": "Patient not found"}`.
- `422 Unprocessable Entity`: a required field is missing or empty.

---

### POST /patients/{patient_id}/clinical-documents/upload-txt

Purpose

Creates a clinical document belonging to the given patient from an uploaded `.txt` file. `document_type` and `title` are sent as form fields alongside the file. The original file itself is uploaded to the configured storage backend (local disk or S3 - see `docs/architecture.md`), in addition to the extracted text stored in `raw_text`.

Accepted file type

`.txt` file extension or `text/plain` content type.

Validation rules

- The file must decode as valid UTF-8 text.
- The decoded text must not be empty.

Success response

`201 Created` - same shape as `POST /patients/{patient_id}/clinical-documents`, with `file_name` set to the uploaded file's name, `file_type` set to `"txt"`, `content_type` set to `"text/plain"`, and `file_size_bytes` set to the uploaded file's size in bytes.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user.
- `422 Unprocessable Entity`: the file is not a `.txt`/`text/plain` file, is not valid UTF-8, or decodes to empty text.
- `503 Service Unavailable`: the configured storage backend could not be reached - see the `503` reference under Error Responses below. Text extraction and validation happen *before* the storage upload, so a request that fails for any of the reasons above never reaches storage at all; this can only happen once the file has already passed every other check.

---

### POST /patients/{patient_id}/clinical-documents/upload-pdf

Purpose

Creates a clinical document belonging to the given patient from an uploaded `.pdf` file, extracting its text content. The original PDF itself is also uploaded to storage - see `upload-txt` above.

Accepted file type

`.pdf` file extension or `application/pdf` content type.

Validation rules

- The file must not be empty.
- The file must be a valid, parseable PDF.
- The PDF must contain extractable text.

Success response

`201 Created` - same shape as `POST /patients/{patient_id}/clinical-documents`, with `file_name` set to the uploaded file's name, `file_type` set to `"pdf"`, `content_type` set to `"application/pdf"`, and `file_size_bytes` set to the uploaded file's size in bytes.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user.
- `422 Unprocessable Entity`: the file is not a `.pdf`/`application/pdf` file, is empty, is malformed, or has no extractable text.
- `503 Service Unavailable`: the configured storage backend could not be reached - see `upload-txt` above.

---

### POST /patients/{patient_id}/clinical-documents/upload-csv

Purpose

Creates a clinical document belonging to the given patient from an uploaded `.csv` file. The CSV's raw text is stored and treated exactly like an uploaded `.txt` file - it becomes ordinary evidence for AI extraction and medication reconciliation. This endpoint never parses the CSV into rows and never creates or modifies `Medication` records; that is a distinct feature (`POST /patients/{patient_id}/medications/import`, see above), unrelated to this one beyond both accepting a `.csv` file. The original CSV itself is also uploaded to storage - see `upload-txt` above.

Accepted file type

`.csv` file extension or `text/csv` content type.

Validation rules

- The file must decode as valid UTF-8 text.
- The decoded text must not be empty.
- No column or row-level validation is performed - unlike `POST /patients/{patient_id}/medications/import`, arbitrary CSV content (or even non-CSV text with a `.csv` name) is accepted, since it is stored as evidence text, not parsed into structured medication rows.

Success response

`201 Created` - same shape as `POST /patients/{patient_id}/clinical-documents`, with `file_name` set to the uploaded file's name, `file_type` set to `"csv"`, `content_type` set to `"text/csv"`, and `file_size_bytes` set to the uploaded file's size in bytes.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user.
- `422 Unprocessable Entity`: the file is not a `.csv`/`text/csv` file, is not valid UTF-8, or decodes to empty text.
- `503 Service Unavailable`: the configured storage backend could not be reached - see `upload-txt` above.

---

### GET /patients/{patient_id}/clinical-documents

Purpose

Returns all clinical documents belonging to the given patient, most recently created first.

Success response

`200 OK` - a list of objects shaped like the `POST /patients/{patient_id}/clinical-documents` response.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user.

---

### GET /patients/{patient_id}/clinical-documents/{document_id}

Purpose

Returns a single clinical document belonging to the given patient.

Success response

`200 OK` - shaped like the `POST /patients/{patient_id}/clinical-documents` response.

404 responses

Returned if `patient_id` does not exist or does not belong to the current user, or if `document_id` does not exist or belongs to a *different* patient - including a different patient owned by the same user. The same response is used in every case so that a caller cannot distinguish a nonexistent document from one it isn't allowed to see.

```json
{
  "detail": "Patient not found"
}
```

```json
{
  "detail": "Clinical document not found"
}
```

---

### GET /patients/{patient_id}/clinical-documents/{document_id}/download

Purpose

Streams the original uploaded file belonging to the given patient's document - the raw bytes that were uploaded via `upload-txt`/`upload-pdf`/`upload-csv`, not the extracted `raw_text`. The response body passes through this server; it is never a redirect to a bucket URL, and the client never learns anything about where or how the file is actually stored.

Response headers

- `Content-Type`: the document's stored `content_type` (`text/plain`, `application/pdf`, or `text/csv`).
- `Content-Disposition`: `attachment; filename="<the original file name>"`.

Success response

`200 OK` - the raw file bytes.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user; `document_id` does not exist or belongs to a different patient (same `"Clinical document not found"` detail as `GET .../{document_id}`); **or** the document exists but has no stored file to download (`{"detail": "This document has no stored file to download"}`) - true for every document created via `POST /patients/{patient_id}/clinical-documents` (pasted text, no file was ever uploaded) and for any document that predates file storage.
- `503 Service Unavailable`: the configured storage backend could not be reached.

---

### DELETE /patients/{patient_id}/clinical-documents/{document_id}

Purpose

Deletes a clinical document belonging to the given patient. This is a real, permanent delete. If the document had a stored file, that object is also deleted from storage - the database record is removed first, and storage deletion is treated as best-effort afterward: if it fails, the request still succeeds (the document is genuinely gone from the API's point of view), and the failure is only logged server-side, never surfaced to the caller. See `docs/architecture.md` for the reasoning.

Success response

`204 No Content`

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user, or the document does not exist or belongs to a different patient.

---

### POST /patients/{patient_id}/analyses

Purpose

Summarizes one or more of the given patient's clinical documents using the configured AI provider, and persists the result as a completed Analysis. Analyses are owned by a `Patient`, not directly by the authenticated user - see `docs/data-model.md`. See `docs/ai.md` for the provider architecture.

`clinical_document_ids` may reference documents just uploaded in the same session or documents already on the patient's record from an earlier visit - this endpoint has never distinguished the two; it only ever validates ownership (see Authorization below), never how or when a document was created. The frontend's `CreateAnalysisPage` reuses this same endpoint to create an analysis purely from previously uploaded documents, with no backend change required. See `docs/frontend.md`.

Authorization

Resolves `patient_id` through the same shared `get_owned_patient` dependency as the medication and clinical-document routes. Every requested `clinical_document_ids` entry must also exist and belong to this same patient - a mixed set spanning more than one patient, or referencing a document belonging to a different patient (including a different patient owned by the same user), is rejected in full and no Analysis is created.

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
  "model": "gemini-2.5-flash",
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

`medications`, `possible_inconsistencies`, and `summary` are the provider's response, parsed as JSON and validated against a Pydantic schema. `analysis_id` identifies the Analysis this request created, whose fields, medication mentions, and inconsistencies are persisted before the response is returned. See `docs/ai.md` for the full response schema.

Medication reconciliation runs automatically as part of this same request: each medication the AI extracted is persisted as supporting evidence and compared against the patient's medication list using the same deterministic reconciliation engine `docs/architecture.md`'s Reconciliation Engine section describes, producing real `MedicationDiscrepancy` rows. Reconciliation results are not summarized in this response body, only in the persisted Analysis, retrievable via `GET /patients/{patient_id}/analyses/{analysis_id}` below. See `docs/architecture.md`'s "Analysis Creation Pipeline" for the full sequence.

If a requested document does not exist or does not belong to this patient, no Analysis is created at all. If the AI provider, persistence, or reconciliation fails after the Analysis is created, it is marked `failed` with a sanitized error message rather than left in an incomplete state, and no discrepancies from that attempt are left partially persisted. See Error Responses below.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user, or a requested document does not exist or does not belong to this patient.
- `422 Unprocessable Entity`: `clinical_document_ids` is missing or empty.
- `503 Service Unavailable`: the AI provider could not produce a usable response, including a missing API key, a request failure, a timeout, malformed JSON, or a response that fails schema validation.

---

### GET /patients/{patient_id}/analyses

Purpose

Returns a page of the given patient's analyses, most recently created first, for use as a "recent analyses" list. Read-only; no query parameter can widen the result beyond this patient's own analyses.

Query parameters

- `limit` (optional, integer, default `10`, minimum `1`, maximum `50`): the maximum number of analyses to return.

Success response

`200 OK`

```json
[
  {
    "id": 7,
    "patient_id": 1,
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
    "open_findings": 1,
    "provider": "gemini",
    "model_name": "gemini-2.5-flash"
  }
]
```

An empty list is returned if the patient has no analyses yet; this is a normal, successful response, not an error. Ordering is by `id` descending, not `created_at`, since rows created together can share an identical `created_at` (Postgres's `now()` is constant within a transaction). Unlike `GET /patients/{patient_id}/analyses/{analysis_id}`, list rows never include `medication_mentions` or `possible_inconsistencies`; fetch the detail endpoint for that.

`open_findings` (added alongside the resolve endpoint above) is the count of this analysis's `medication_discrepancies` whose `resolution_status` is still `"open"` - computed live on every request, unlike `total_findings` and the three severity counts, which are fixed at analysis-completion time and never change afterward. A discrepancy resolved or dismissed after the analysis completed lowers `open_findings` without changing `total_findings`, so this field - not the static counts - is what Patient Overview and the Dashboard use to show how much of an analysis's findings still need review.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user.
- `422 Unprocessable Entity`: `limit` is outside the `1`-`50` range.

---

### GET /patients/{patient_id}/analyses/{analysis_id}

Purpose

Returns the metadata and persisted results of one of the given patient's analyses. Read-only: it does not create, rerun, or modify an analysis. See `docs/data-model.md` for the underlying `Analysis`, `AnalysisMedicationMention`, `AnalysisInconsistency`, and `MedicationDiscrepancy` models.

Success response

`200 OK`

```json
{
  "id": 7,
  "patient_id": 1,
  "status": "completed",
  "provider": "gemini",
  "model_name": "gemini-2.5-flash",
  "summary": "...",
  "started_at": "2026-07-12T19:59:14.696845Z",
  "completed_at": "2026-07-12T19:59:16.112249Z",
  "error_message": null,
  "created_at": "2026-07-12T19:59:14.500000Z",
  "updated_at": "2026-07-12T19:59:16.112249Z",
  "document_count": 1,
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
  ],
  "medication_discrepancies": [
    {
      "id": 5,
      "analysis_id": 7,
      "medication_id": null,
      "medication_mention_id": 3,
      "discrepancy_type": "missing_from_medication_list",
      "severity": "high",
      "title": "Lisinopril not found in medication list",
      "ai_explanation": "Lisinopril is mentioned in the selected clinical documents but does not appear in the current medication list.",
      "recommendation": null,
      "expected_value": null,
      "observed_value": "Lisinopril",
      "resolution_status": "open",
      "created_at": "2026-07-12T19:59:16.000000Z",
      "updated_at": null,
      "medication": null,
      "medication_mention": {
        "id": 3,
        "medication_name": "Lisinopril",
        "dose": "10 mg",
        "route": "oral",
        "frequency": "once daily",
        "status": "active",
        "context_text": "Patient takes Lisinopril 10mg oral daily.",
        "clinical_document": {
          "id": 4,
          "title": "March Visit Note",
          "document_type": "visit_note"
        }
      }
    }
  ]
}
```

`medication_mentions`, `possible_inconsistencies`, and `medication_discrepancies` are always returned, sorted by ascending `id`, even for analyses that have none (an empty list) or that failed before persisting any results (all three lists empty, `summary`, `provider`, and `model_name` are `null`).

`document_count` is `len(analysis.clinical_documents)` - how many clinical documents this analysis covers (a computed property on the model, not a stored column, the same pattern as `ClinicalDocument.analysis_count`; also present on `AnalysisSummaryResponse` below). The Analysis Results page's AI Summary metadata shows it alongside `provider`/`model_name`/`completed_at` without a second request.

`medication_discrepancies` are the deterministic reconciliation engine's findings - see `docs/architecture.md`'s Reconciliation Engine and Analysis Creation Pipeline sections for how they are produced during `POST /patients/{patient_id}/analyses`. `medication_mention_id`/`medication_id` are the raw foreign keys; each discrepancy also nests the evidence those ids point to, so the Analysis Results page can render supporting evidence without a second request:

- `medication_mention`, present when `medication_mention_id` is set: the `MedicationMention` extracted as supporting evidence, including `context_text` (the relevant text snippet, when the AI provided one) and a nested `clinical_document` - a minimal citation (`id`, `title`, `document_type`) of the source document, deliberately not the full document (no `raw_text`), since a citation has no need for it.
- `medication`, present when `medication_id` is set instead: the patient's own `Medication` row (the full existing `MedicationResponse` shape), for findings like `unsupported_medication_list_entry` where the evidence is "this is on the list but was never mentioned," not an extracted mention.

Either, both, or neither may be `null`, matching the nullability of the two source foreign keys (both `ON DELETE SET NULL`, so a discrepancy always survives its linked medication or mention being deleted, just with that piece of evidence now missing). `MedicationMention` has no API exposure anywhere else in the app; this nested, read-only view is the only place its fields are ever serialized.

`error_message` is `null` unless `status` is `"failed"`, in which case it holds the same sanitized message returned by `POST /patients/{patient_id}/analyses` at failure time (see that endpoint's `503` response above). It never contains a stack trace, a provider exception, `ValidationError` details, raw AI output, or a raw SQL error; only the sanitized message already stored on the Analysis is exposed.

404 responses

Returned if `patient_id` does not exist or does not belong to the current user, or if `analysis_id` does not exist or belongs to a *different* patient - including a different patient owned by the same user. The same response is used in every case so that a caller cannot distinguish a nonexistent analysis from one it isn't allowed to see.

```json
{
  "detail": "Patient not found"
}
```

```json
{
  "detail": "Analysis not found"
}
```

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user, or the analysis does not exist or belongs to a different patient.

---

### DELETE /patients/{patient_id}/analyses/{analysis_id}

Purpose

Permanently deletes one of the given patient's analyses, along with its persisted `AnalysisMedicationMention`, `AnalysisInconsistency`, and `MedicationDiscrepancy` rows. Does not delete clinical documents, medications, or any other reusable resource; only data scoped to this analysis is removed.

Success response

`204 No Content`

No response body. After a successful delete, `GET /patients/{patient_id}/analyses/{analysis_id}` for the same id returns `404`.

404 responses

Returned if `patient_id` does not exist or does not belong to the current user, or if `analysis_id` does not exist or belongs to a different patient, using the same responses as `GET /patients/{patient_id}/analyses/{analysis_id}` so a caller cannot distinguish a nonexistent analysis from one it isn't allowed to see.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user, or the analysis does not exist or belongs to a different patient.

---

### POST /patients/{patient_id}/analyses/{analysis_id}/discrepancies/{discrepancy_id}/resolve

Purpose

Records a provider's resolution of one medication discrepancy - accepting it (creating or updating the patient's medication list accordingly) or dismissing it - and persists a full audit trail on the discrepancy itself. See `docs/architecture.md`'s Reconciliation Engine section and `docs/data-model.md`'s `MedicationDiscrepancy` entity for how this fits into the wider reconciliation workflow.

Authorization

Resolves `patient_id` through the same shared `get_owned_patient` dependency as every other patient-nested route. `analysis_id` must belong to this patient, and `discrepancy_id` must belong to this analysis - each is checked with its own scoped lookup and returns `404` independently, the same "can't distinguish nonexistent from not-yours" pattern used throughout this API.

Request body

```json
{
  "action": "update_medication",
  "dose": "20 mg",
  "note": "Confirmed with patient by phone."
}
```

- `action` is required: one of `add_medication`, `update_medication`, `dismiss`.
- `medication_name`, `dose`, `route`, `frequency`, `status` are optional and only relevant for `add_medication`/`update_medication` - each, if present, must be non-empty.
- `note` is an optional, freeform provider rationale, stored regardless of `action`.
- Extra fields are rejected (`extra="forbid"`).

Which `action` is valid depends on the discrepancy's own `discrepancy_type`:

| `discrepancy_type` | Valid `action` values | Notes |
|---|---|---|
| `missing_from_medication_list` | `add_medication`, `dismiss` | `add_medication` requires `medication_name`, `dose`, `route`, `frequency`, and `status` all present - it creates a new `Medication` (`source: "reconciliation"`) and links it to the discrepancy. |
| `dose_conflict`, `route_conflict`, `frequency_conflict`, `discontinued_status_conflict`, `status_conflict`, `unsupported_medication_list_entry` | `update_medication`, `dismiss` | `update_medication` requires at least one of `medication_name`/`dose`/`route`/`frequency`/`status`; only the fields present are changed on the existing linked `Medication`. There is no dedicated "mark discontinued" or "mark active" action - both are `update_medication` with `status` set to the desired value; the UI supplies that value, not the API. |

`dismiss` is valid for every discrepancy type and never creates or modifies a `Medication` row.

Success response

`200 OK` - the full `MedicationDiscrepancyDetailResponse` shape (see `GET /patients/{patient_id}/analyses/{analysis_id}` above), reflecting the new resolution state:

```json
{
  "id": 5,
  "analysis_id": 7,
  "medication_id": 12,
  "medication_mention_id": 3,
  "discrepancy_type": "missing_from_medication_list",
  "severity": "high",
  "title": "Lisinopril not found in medication list",
  "ai_explanation": "Lisinopril is mentioned in the selected clinical documents but does not appear in the current medication list.",
  "recommendation": null,
  "expected_value": null,
  "observed_value": "Lisinopril",
  "resolution_status": "resolved",
  "resolution_action": "add_medication",
  "resolved_at": "2026-07-13T09:15:00.000000Z",
  "resolution_note": "Confirmed with patient by phone.",
  "created_at": "2026-07-12T19:59:16.000000Z",
  "updated_at": "2026-07-13T09:15:00.000000Z",
  "medication": { "...": "the newly created or updated Medication" },
  "medication_mention": { "...": "unchanged, same as before resolving" },
  "resolved_by": {
    "id": 1,
    "name": "Jane Doe",
    "username": "jane_doe",
    "email": "jane@example.com"
  }
}
```

`resolution_status` becomes `"resolved"` for `add_medication`/`update_medication`, or `"dismissed"` for `dismiss` - the same `ResolutionStatus` enum `docs/data-model.md` already documents, reused unchanged rather than introducing a parallel status. `resolution_action`, `resolved_at`, `resolution_note`, and `resolved_by` are the audit trail added by this endpoint; all four are `null`/absent until a discrepancy is resolved, and none of the fields the original reconciliation run computed (`title`, `ai_explanation`, `expected_value`, `observed_value`, ...) are ever changed by resolving - the finding itself remains a permanent, unaltered record. `resolved_by.username` is `null` for a resolver whose account predates usernames and hasn't set one since - the frontend falls back to `name`, then `email`, when it is.

Possible error responses

- `400 Bad Request`: `action` doesn't make sense for this discrepancy's `discrepancy_type` (see table above), required fields are missing for the chosen action, or (defensively) the linked medication no longer belongs to this patient.

  ```json
  {
    "detail": "add_medication is only valid for a medication missing from the list"
  }
  ```

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user, `analysis_id` does not exist or does not belong to this patient, or `discrepancy_id` does not exist or does not belong to this analysis.
- `409 Conflict`: this discrepancy has already been resolved or dismissed. Resolving is one-way - there is no "re-open" or "undo" action.

  ```json
  {
    "detail": "Discrepancy 5 has already been resolved"
  }
  ```

- `422 Unprocessable Entity`: `action` is missing or not a recognized value, an included field is empty, or an extra field is present.

---

### GET /analyses/recent

Purpose

The Dashboard's Recent Analyses feed. Unlike every other analyses endpoint, this one is **not** nested under `/patients/{patient_id}` - it spans every patient the current user owns, since the Dashboard is a cross-patient entry point, not a single patient's own page. Read-only.

Query parameters

- `limit` (optional, integer, default `10`, minimum `1`, maximum `50`): the maximum number of analyses to return - the same bounds as `GET /patients/{patient_id}/analyses`.

Success response

`200 OK`

```json
[
  {
    "id": 7,
    "patient_id": 1,
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
    "open_findings": 1,
    "provider": "gemini",
    "model_name": "gemini-2.5-flash",
    "patient": {
      "id": 1,
      "first_name": "Jane",
      "last_name": "Doe"
    }
  }
]
```

Identical to `AnalysisSummaryResponse` (see `GET /patients/{patient_id}/analyses` above) with one addition: a nested `patient` object (`id`, `first_name`, `last_name` only - just enough to identify whose analysis this is, the same "citation, not the full resource" shape as `ClinicalDocumentSummaryResponse`), since the caller has no `patient_id` in the URL to already know this from. Ordering is by `id` descending, across every patient, for the same reason `GET /patients/{patient_id}/analyses` isn't ordered by `created_at`. Analyses belonging to archived patients are excluded, the same exclusion `GET /patients` already applies to the patient list itself.

An empty list is returned if the user has no analyses across any of their patients yet; this is a normal, successful response, not an error.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `422 Unprocessable Entity`: `limit` is outside the `1`-`50` range.

---

## File Uploads

Clinical documents can enter the system three ways: pasted text (JSON), or an uploaded file (`multipart/form-data`). Every route below is fully documented under its own entry above; this section is a consolidated summary of the pattern they share.

### Pasted text

`POST /patients/{patient_id}/clinical-documents` takes an ordinary JSON body (`document_type`, `title`, `raw_text`) - there is no file involved. The resulting document has `file_name`, `content_type`, and `file_size_bytes` all `null`, and `file_type` set to `"manual_entry"`. It has nothing to download: `GET .../{document_id}/download` 404s for it.

### File upload

| Endpoint | Accepted file | Stored `file_type` | Stored `content_type` |
|---|---|---|---|
| `POST /patients/{patient_id}/clinical-documents/upload-txt` | `.txt` extension or `text/plain` | `"txt"` | `"text/plain"` |
| `POST /patients/{patient_id}/clinical-documents/upload-pdf` | `.pdf` extension or `application/pdf` | `"pdf"` | `"application/pdf"` |
| `POST /patients/{patient_id}/clinical-documents/upload-csv` | `.csv` extension or `text/csv` | `"csv"` | `"text/csv"` |

All three are `multipart/form-data` requests with the same three parts:

```http
POST /patients/1/clinical-documents/upload-txt HTTP/1.1
Content-Type: multipart/form-data; boundary=...

--...
Content-Disposition: form-data; name="document_type"

visit_note
--...
Content-Disposition: form-data; name="title"

Initial Visit
--...
Content-Disposition: form-data; name="file"; filename="visit-note.txt"
Content-Type: text/plain

Patient presents with hypertension.
--...--
```

`document_type` and `title` are plain form fields (not part of the file), both required and non-empty. Extension and content type are checked independently - either one matching is enough, so a file with a generic `application/octet-stream` content type but a correct extension is still accepted, and vice versa. Text is extracted server-side (a plain UTF-8 decode for `.txt`/`.csv`, `pypdf` for `.pdf`) into the same `raw_text` field a pasted-text document has, so AI analysis (`POST /patients/{patient_id}/analyses`) treats every document identically regardless of how it was created.

**Both** the extracted text and the original file bytes are kept: `raw_text` is stored in Postgres exactly as with pasted text, and the original file is separately uploaded to the configured storage backend (`STORAGE_BACKEND=local` or `s3` - see `docs/deployment.md`) under a generated key never exposed over the API. `content_type` and `file_size_bytes` on the response reflect that stored file.

### Downloading the original file

`GET /patients/{patient_id}/clinical-documents/{document_id}/download` streams the original uploaded file's bytes back through this server - never a redirect to a bucket URL, and the response never reveals a storage path or key. Response headers:

- `Content-Type`: the document's stored `content_type`.
- `Content-Disposition`: `attachment; filename="<original file name>"`.

A pasted-text document, or any document with no stored file, 404s here (`"This document has no stored file to download"`) rather than returning an empty body.

### Two different `.csv` endpoints

`POST /patients/{patient_id}/medications/import` and `POST /patients/{patient_id}/clinical-documents/upload-csv` both accept a `.csv` file but do unrelated things - the former parses it into structured `Medication` rows, the latter stores its raw text as ordinary clinical-document evidence. See each endpoint's own entry above, and the Notes section below, for the full distinction.

---

## Error Responses

### 400 Bad Request

Returned only by `POST /patients/{patient_id}/analyses/{analysis_id}/discrepancies/{discrepancy_id}/resolve`, when the requested `action` doesn't make sense for that discrepancy's `discrepancy_type` or current medication linkage (see that endpoint's table above) - a request that is well-formed JSON and passes schema validation, but is semantically invalid given the resource's current state. No other endpoint returns this status; request *body* validation failures (missing/malformed fields) surface as `422` instead (see below).

```json
{
  "detail": "add_medication is only valid for a medication missing from the list"
}
```

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

Returned when a requested resource does not exist, or exists but does not belong to the authenticated user (directly, or via a patient it doesn't belong to). Both cases return the same response so that a caller cannot tell the two apart. Used by the patient-nested `medications`, `clinical-documents`, and `analyses` endpoints, among others.

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

Returned by `POST /auth/register` and `PATCH /users/me` when the given email is already registered, or the given username is already taken (case-insensitively) by a different user.

```json
{
  "detail": "A user with this email is already registered"
}
```

```json
{
  "detail": "This username is already taken"
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

Returned by `POST /patients/{patient_id}/analyses` when the configured AI provider cannot produce a response, including a missing API key, a request failure, a timeout, or an invalid response.

```json
{
  "detail": "Gemini API key is not configured"
}
```

Also returned by `POST /patients/{patient_id}/clinical-documents/upload-txt`/`upload-pdf`/`upload-csv` and `GET .../{document_id}/download` when the configured storage backend (local disk or S3) cannot be reached:

```json
{
  "detail": "File storage is currently unavailable"
}
```

---

## API Conventions

**Pagination.** Only `GET /patients/{patient_id}/analyses` and `GET /analyses/recent` paginate, and only in the limited sense of a `limit` query parameter (integer, default `10`, minimum `1`, maximum `50`) - there is no `offset`, page number, or cursor, and no way to fetch anything past the most recent `limit` results. Every other list endpoint (`GET /patients`, `GET /patients/{patient_id}/medications`, `GET /patients/{patient_id}/clinical-documents`) returns the full, unpaginated list.

**Timestamps.** Every `created_at`/`updated_at`/`started_at`/`completed_at`/`resolved_at` field is UTC, serialized by Pydantic from a `datetime` column (e.g. `"2026-07-12T19:59:14.696845Z"`). The one exception is `GET /health`'s `timestamp`, a plain pre-formatted string (`"2026-08-04T02:15:30Z"`, no microseconds) rather than a serialized `datetime` field - see that endpoint's field notes above for why. `updated_at` is `null` until a resource is actually updated for the first time; creation alone never sets it.

**IDs.** Every resource is identified by an integer primary key, assigned by the database on creation - never a UUID or client-supplied id. Ownership is enforced by scoping every query to the authenticated user (directly, e.g. `Patient.user_id`, or transitively through `patient_id`, e.g. medications/clinical documents/analyses) - an id that exists but belongs to someone else is indistinguishable from one that doesn't exist at all: both 404, never `403 Forbidden` (see 404 Not Found above).

**Nullable fields.** A field that is optional at creation (e.g. `Patient.external_mrn`, `Medication.notes`) is `null`, never omitted, in every response - the response schemas list every field explicitly rather than using `exclude_unset`/`exclude_none` (the one exception is `GET /health`, which does use `exclude_none` - see that endpoint). On `PATCH` endpoints, a field left out of the *request* body is left unchanged, which is a different thing from explicitly setting it to `null`; where a field can be intentionally cleared this way (e.g. `username` on `PATCH /users/me`), that's called out in the endpoint's own validation rules.

**Enum values.** Every enum (see Schemas above) is a plain lowercase, `snake_case` string over the wire - `"pending"`, `"dose_conflict"`, `"add_medication"`, and so on - never an integer code.

**Consistent response patterns.** `POST` that creates a resource returns `201` with the created resource; `PATCH` returns `200` with the updated resource; `DELETE` returns `204` with no body. A partial update (`PATCH`) never requires resending fields the caller isn't changing. A handful of request schemas (`UserUpdate`, `DiscrepancyResolutionIn`) reject unrecognized fields outright (`extra="forbid"`, surfacing as `422`) rather than silently ignoring them; most others (e.g. `PatientUpdate`) simply ignore an unrecognized field. Soft-delete exists only for `Patient` (`DELETE /patients/{patient_id}` sets `status: "archived"`, does not remove the row); every other `DELETE` endpoint is a real, permanent delete.

---

## OpenAPI / Interactive Docs

This document is written and maintained by hand, alongside the code - it is not generated. FastAPI separately generates a full OpenAPI 3 schema directly from the route decorators, Pydantic models, and type hints in `app/`, always exactly in sync with the running code:

- `GET /docs` - interactive Swagger UI. Every endpoint below can be tried directly from the browser, including sending a Bearer token via the "Authorize" button.
- `GET /openapi.json` - the raw OpenAPI schema, useful for generating a typed client or importing into a tool like Postman/Insomnia.

Where this document explains *why* something works the way it does (a workflow, a validation rule's reasoning, which endpoints share a schema), the OpenAPI schema is the authoritative source for the exact shape of a request or response - field types, which fields are required, and full enum definitions. If the two ever disagree, the running code (and therefore `/openapi.json`) is correct and this document is stale.

---

## Notes

This API currently supports authentication, application infrastructure, patient management, and patient-scoped clinical document management, medication list management, and AI-generated document summaries persisted as analyses, including listing, retrieval, and deletion of a patient's own analyses (`/`, `/health`, `/auth/register`, `/auth/login`, `/users/me`, `/patients`, `/patients/{patient_id}/medications`, `/patients/{patient_id}/clinical-documents`, `/patients/{patient_id}/analyses`). Medication, ClinicalDocument, and Analysis are owned solely through `Patient` - `patient_id` is their only ownership column (see `docs/data-model.md` for the migration history), and there is no flat `/medications`, `/clinical-documents`, `/ai/summarize`, or `/ai/analyses` route. `User` is used only for authentication and for owning `Patient` directly. Medication reconciliation runs automatically as part of `POST /patients/{patient_id}/analyses` and its findings are exposed via `medication_discrepancies` on `GET /patients/{patient_id}/analyses/{analysis_id}`; a provider resolves or dismisses each finding via `POST .../discrepancies/{discrepancy_id}/resolve`, which is also the only endpoint that lets resolving a discrepancy create or update a `Medication` row on the provider's behalf.

`GET /analyses/recent` is the one exception to "every analysis is reached through its patient": a cross-patient feed for the Dashboard's Recent Analyses section, scoped to the current user (via the same `get_current_user` dependency every other endpoint uses) rather than nested under a single `patient_id`.

Two unrelated endpoints both accept a `.csv` file, and are easy to confuse: `POST /patients/{patient_id}/medications/import` parses the CSV into rows and directly creates `Medication` records, while `POST /patients/{patient_id}/clinical-documents/upload-csv` stores the CSV's raw text as an ordinary clinical document - evidence for AI extraction and reconciliation, never imported into the patient's medication list. Uploading the same CSV to both is a legitimate, deliberate action (e.g. importing a medication list *and* including it as analysis evidence), not a bug; the two pipelines never call into each other.

**File storage.** Uploading a document via `upload-txt`/`upload-pdf`/`upload-csv` persists the *original file* (not just its extracted text) to a configured storage backend - local disk by default, or S3, selected by the `STORAGE_BACKEND` environment variable (see `docs/deployment.md`). `GET .../{document_id}/download` streams it back; the response never redirects to a bucket URL, and no endpoint anywhere ever returns an S3 URL or object key. A document created via the plain `POST /patients/{patient_id}/clinical-documents` (pasted text) has no file at all and 404s from the download endpoint. AI analysis is entirely unaffected - it has always read `raw_text` from Postgres and continues to; it never touches the storage backend, whether a document has a stored file or not.
