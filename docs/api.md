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

### POST /patients/{patient_id}/medications

Purpose

Creates a medication entry in the given patient's medication list. As of Sprint 3.5 (Issue #129), medications are owned by a `Patient`, not directly by the authenticated user - see `docs/data-model.md`.

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

Creates a clinical document from pasted text, belonging to the given patient. As of Sprint 3.5 (Issue #130), clinical documents are owned by a `Patient`, not directly by the authenticated user - see `docs/data-model.md`.

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
  "created_at": "2026-07-12T19:59:14.696845Z",
  "updated_at": null,
  "analysis_count": 0
}
```

`analysis_count` (added in Issue #146) is `len(document.analyses)` - how many analyses this document has been included in via `POST /patients/{patient_id}/analyses`'s `clinical_document_ids` (a computed property on the model, not a stored column; the same pattern as `AnalysisSummaryResponse.document_count`). A brand-new document always starts at `0`. There is no file-size field: the backend never stores an uploaded file's original bytes, only its extracted `raw_text`, so no real byte count exists anywhere to expose - `len(raw_text)` would not be a file size and is not substituted for one.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user - `{"detail": "Patient not found"}`.
- `422 Unprocessable Entity`: a required field is missing or empty.

---

### POST /patients/{patient_id}/clinical-documents/upload-txt

Purpose

Creates a clinical document belonging to the given patient from an uploaded `.txt` file. `document_type` and `title` are sent as form fields alongside the file.

Accepted file type

`.txt` file extension or `text/plain` content type.

Validation rules

- The file must decode as valid UTF-8 text.
- The decoded text must not be empty.

Success response

`201 Created` - same shape as `POST /patients/{patient_id}/clinical-documents`, with `file_name` set to the uploaded file's name and `file_type` set to `"txt"`.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user.
- `422 Unprocessable Entity`: the file is not a `.txt`/`text/plain` file, is not valid UTF-8, or decodes to empty text.

---

### POST /patients/{patient_id}/clinical-documents/upload-pdf

Purpose

Creates a clinical document belonging to the given patient from an uploaded `.pdf` file, extracting its text content.

Accepted file type

`.pdf` file extension or `application/pdf` content type.

Validation rules

- The file must not be empty.
- The file must be a valid, parseable PDF.
- The PDF must contain extractable text.

Success response

`201 Created` - same shape as `POST /patients/{patient_id}/clinical-documents`, with `file_name` set to the uploaded file's name and `file_type` set to `"pdf"`.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user.
- `422 Unprocessable Entity`: the file is not a `.pdf`/`application/pdf` file, is empty, is malformed, or has no extractable text.

---

### POST /patients/{patient_id}/clinical-documents/upload-csv

Purpose

Creates a clinical document belonging to the given patient from an uploaded `.csv` file (Issue #164). The CSV's raw text is stored and treated exactly like an uploaded `.txt` file - it becomes ordinary evidence for AI extraction and medication reconciliation. This endpoint never parses the CSV into rows and never creates or modifies `Medication` records; that is a distinct feature (`POST /patients/{patient_id}/medications/import`, see above), unrelated to this one beyond both accepting a `.csv` file.

Accepted file type

`.csv` file extension or `text/csv` content type.

Validation rules

- The file must decode as valid UTF-8 text.
- The decoded text must not be empty.
- No column or row-level validation is performed - unlike `POST /patients/{patient_id}/medications/import`, arbitrary CSV content (or even non-CSV text with a `.csv` name) is accepted, since it is stored as evidence text, not parsed into structured medication rows.

Success response

`201 Created` - same shape as `POST /patients/{patient_id}/clinical-documents`, with `file_name` set to the uploaded file's name and `file_type` set to `"csv"`.

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user.
- `422 Unprocessable Entity`: the file is not a `.csv`/`text/csv` file, is not valid UTF-8, or decodes to empty text.

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

### DELETE /patients/{patient_id}/clinical-documents/{document_id}

Purpose

Deletes a clinical document belonging to the given patient. This is a real, permanent delete.

Success response

`204 No Content`

Possible error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: `patient_id` does not exist or does not belong to the current user, or the document does not exist or belongs to a different patient.

---

### POST /patients/{patient_id}/analyses

Purpose

Summarizes one or more of the given patient's clinical documents using the configured AI provider, and persists the result as a completed Analysis. As of Sprint 3.5 (Issue #130), analyses are owned by a `Patient`, not directly by the authenticated user - see `docs/data-model.md`. See `docs/ai.md` for the provider architecture.

`clinical_document_ids` may reference documents just uploaded in the same session or documents already on the patient's record from an earlier visit - this endpoint has never distinguished the two; it only ever validates ownership (see Authorization below), never how or when a document was created. Issue #145 added a frontend flow (`SelectDocumentsPage`) that reuses this same endpoint to create an analysis purely from previously uploaded documents, with no backend change required. See `docs/frontend.md`.

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

`medications`, `possible_inconsistencies`, and `summary` are the provider's response, parsed as JSON and validated against a Pydantic schema. `analysis_id` identifies the Analysis this request created, whose fields, medication mentions, and inconsistencies are persisted before the response is returned. See `docs/ai.md` for the full response schema.

As of Issue #148, medication reconciliation now runs automatically as part of this same request: each medication the AI extracted is persisted as supporting evidence and compared against the patient's medication list using the same deterministic reconciliation engine `docs/architecture.md`'s Reconciliation Engine section describes, producing real `MedicationDiscrepancy` rows rather than the empty findings this endpoint always returned before. This response body is unchanged by that - reconciliation results are not summarized here, only in the persisted Analysis, retrievable via `GET /patients/{patient_id}/analyses/{analysis_id}` below. See `docs/architecture.md`'s "Analysis Creation Pipeline" for the full sequence.

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
    "model_name": "gemini-2.0-flash"
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
  "model_name": "gemini-2.0-flash",
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

`document_count` (added in Issue #47) is `len(analysis.clinical_documents)` - how many clinical documents this analysis covers (a computed property on the model, not a stored column, the same pattern as `ClinicalDocument.analysis_count`; also present on `AnalysisSummaryResponse` below). The Analysis Results page's AI Summary metadata shows it alongside `provider`/`model_name`/`completed_at` without a second request.

`medication_discrepancies` (added in Issue #148) are the deterministic reconciliation engine's findings - see `docs/architecture.md`'s Reconciliation Engine and Analysis Creation Pipeline sections for how they are produced during `POST /patients/{patient_id}/analyses`. `medication_mention_id`/`medication_id` are the raw foreign keys; as of Issue #46, each discrepancy also nests the evidence those ids point to, so the Analysis Results page can render supporting evidence without a second request:

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
    "email": "jane@example.com"
  }
}
```

`resolution_status` becomes `"resolved"` for `add_medication`/`update_medication`, or `"dismissed"` for `dismiss` - the same `ResolutionStatus` enum `docs/data-model.md` already documents, reused unchanged rather than introducing a parallel status. `resolution_action`, `resolved_at`, `resolution_note`, and `resolved_by` are the audit trail added by this endpoint; all four are `null`/absent until a discrepancy is resolved, and none of the fields the original reconciliation run computed (`title`, `ai_explanation`, `expected_value`, `observed_value`, ...) are ever changed by resolving - the finding itself remains a permanent, unaltered record.

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

Issue #157: the Dashboard's Recent Analyses feed. Unlike every other analyses endpoint, this one is **not** nested under `/patients/{patient_id}` - it spans every patient the current user owns, since the Dashboard is a cross-patient entry point, not a single patient's own page. Read-only.

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
    "model_name": "gemini-2.0-flash",
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

Returned by `POST /patients/{patient_id}/analyses` when the configured AI provider cannot produce a response, including a missing API key, a request failure, a timeout, or an invalid response.

```json
{
  "detail": "Gemini API key is not configured"
}
```

---

## Notes

This API currently supports authentication, application infrastructure, patient management, and patient-scoped clinical document management, medication list management, and AI-generated document summaries persisted as analyses, including listing, retrieval, and deletion of a patient's own analyses (`/`, `/health`, `/auth/register`, `/auth/login`, `/users/me`, `/patients`, `/patients/{patient_id}/medications`, `/patients/{patient_id}/clinical-documents`, `/patients/{patient_id}/analyses`). Medication, ClinicalDocument, and Analysis are owned solely through `Patient` - `patient_id` is their only ownership column (Sprint 3.5, Issue #133 removed the transitional `user_id` these three tables carried during the migration; see `docs/data-model.md`), and the earlier flat `/medications`, `/clinical-documents`, `/ai/summarize`, and `/ai/analyses` routes no longer exist. `User` is used only for authentication and for owning `Patient` directly. Medication reconciliation runs automatically as part of `POST /patients/{patient_id}/analyses` (Issue #148) and its findings are exposed via `medication_discrepancies` on `GET /patients/{patient_id}/analyses/{analysis_id}`; a provider resolves or dismisses each finding via `POST .../discrepancies/{discrepancy_id}/resolve`, which is also the only endpoint that lets resolving a discrepancy create or update a `Medication` row on the provider's behalf.

Issue #157 added the first exception to "every analysis is reached through its patient": `GET /analyses/recent`, a cross-patient feed for the Dashboard's Recent Analyses section, scoped to the current user (via the same `get_current_user` dependency every other endpoint uses) rather than nested under a single `patient_id`.

Two unrelated endpoints both accept a `.csv` file, and are easy to confuse: `POST /patients/{patient_id}/medications/import` (Sprint 3.5) parses the CSV into rows and directly creates `Medication` records, while `POST /patients/{patient_id}/clinical-documents/upload-csv` (Issue #164) stores the CSV's raw text as an ordinary clinical document - evidence for AI extraction and reconciliation, never imported into the patient's medication list. Uploading the same CSV to both is a legitimate, deliberate action (e.g. importing a medication list *and* including it as analysis evidence), not a bug; the two pipelines never call into each other.
