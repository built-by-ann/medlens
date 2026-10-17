# API Reference

MedLens exposes a REST API built with FastAPI. This doc covers conventions, the endpoint list, and behavior that isn't obvious from the schema.

For exact request/response shapes, field types, and enums, use the generated OpenAPI docs. They come straight from the code and can't drift:

- `GET /docs`: interactive Swagger UI (use "Authorize" to send a token)
- `GET /openapi.json`: raw schema

## Base URL

- **Through the app:** `https://<origin>/api/...`. nginx strips the `/api` prefix, so `POST /api/auth/login` reaches `POST /auth/login`. This is what the browser uses.
- **Direct:** `http://localhost:8000` when running uvicorn locally, or from the host running Compose. The backend container is not publicly exposed (see [deployment.md](deployment.md)).

## Authentication

1. `POST /auth/register` with `email`, `password` (8+ chars), `username`, and optional `name`. Returns the user, **not** a token.
2. `POST /auth/login` with `email` and `password`. Returns `{ "access_token": "<jwt>", "token_type": "bearer" }`.
3. Send `Authorization: Bearer <jwt>` on every other request.

Tokens carry the user id in `sub` and expire after `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default 30). There is no refresh token and no logout endpoint. Only `/`, `/health`, `/auth/register`, and `/auth/login` are public.

Usernames are 3 to 30 characters (`a-z A-Z 0-9 _ .`) and unique case-insensitively. Login returns the same 401 for an unknown email and a wrong password.

## Conventions

- **Ownership:** every patient-nested route resolves `patient_id` through `get_owned_patient`. A resource that exists but belongs to someone else returns **404, never 403**, so callers can't probe for existence.
- **Status codes:** create returns `201` with the resource, `PATCH` returns `200` with the resource, and `DELETE` returns `204`.
- **PATCH** is partial: omitted fields are unchanged. `UserUpdate` and `DiscrepancyResolutionIn` reject unknown fields (422). Other update schemas ignore them.
- **Deletes** are permanent except for patients, which are archived (soft delete).
- **IDs** are integer primary keys.
- **Timestamps** are UTC ISO-8601. `updated_at` is `null` until the first update.
- **Nullable fields** are returned as `null`, never omitted.
- **Enums** are lowercase snake_case strings.
- **Pagination:** only the two analyses list endpoints accept `limit` (1 to 50, default 10). There is no offset or cursor. All other lists return everything.
- **Ordering:** analyses lists sort by `id` descending, because rows created in one transaction can share `created_at`.

## Endpoints

### System

| Method | Path | Notes |
|---|---|---|
| GET | `/` | Welcome message |
| GET | `/health` | App, DB, storage, and AI config. `503` if the DB check fails. Makes no external calls (only `SELECT 1`). |

### Users

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | `409` on duplicate email or username |
| POST | `/auth/login` | Returns JWT |
| GET | `/users/me` | Current profile. `username` may be `null` on older accounts. |
| PATCH | `/users/me` | Any of `email`, `name`, `username`. Setting `username` to `null` clears it. No password changes. |

### Patients

| Method | Path | Notes |
|---|---|---|
| POST | `/patients` | `first_name`, `last_name`, and `date_of_birth` are required. `status` always starts `active`. |
| GET | `/patients` | Active patients only |
| GET | `/patients/{id}` | Any status, including archived |
| PATCH | `/patients/{id}` | `status` is ignored. Archive via DELETE instead. |
| DELETE | `/patients/{id}` | Archives the patient. Children stay reachable. There is no un-archive. |

### Medications

All under `/patients/{patient_id}`.

| Method | Path | Notes |
|---|---|---|
| POST | `/medications` | `medication_name`, `dose`, `route`, `frequency`, `status`, and `source` are required and non-empty |
| POST | `/medications/import` | CSV import (see below) |
| GET | `/medications` | |
| GET / PATCH / DELETE | `/medications/{medication_id}` | |

### Clinical documents

All under `/patients/{patient_id}`.

| Method | Path | Notes |
|---|---|---|
| POST | `/clinical-documents` | JSON `document_type`, `title`, `raw_text`. `file_type: "manual_entry"`, no stored file. |
| POST | `/clinical-documents/upload-txt` | multipart: `document_type`, `title`, `file` |
| POST | `/clinical-documents/upload-pdf` | Same, with text extracted via `pypdf` |
| POST | `/clinical-documents/upload-csv` | Same; stored as evidence text only |
| GET | `/clinical-documents` | Newest first |
| GET | `/clinical-documents/{document_id}` | Includes `analysis_count` |
| GET | `/clinical-documents/{document_id}/download` | Streams the original file. `404` if the document has no stored file. |
| DELETE | `/clinical-documents/{document_id}` | Storage cleanup is best-effort and logged on failure |

### Analyses

| Method | Path | Notes |
|---|---|---|
| POST | `/patients/{patient_id}/analyses` | `{ "clinical_document_ids": [...] }`. Runs AI extraction and reconciliation synchronously. |
| GET | `/patients/{patient_id}/analyses?limit=` | Summaries with finding counts |
| GET | `/patients/{patient_id}/analyses/{analysis_id}` | Full detail including mentions, inconsistencies, and discrepancies |
| DELETE | `/patients/{patient_id}/analyses/{analysis_id}` | Also deletes its mentions, inconsistencies, and discrepancies |
| POST | `/patients/{patient_id}/analyses/{analysis_id}/discrepancies/{discrepancy_id}/resolve` | See below |
| GET | `/analyses/recent?limit=` | Cross-patient feed for the Dashboard. Excludes archived patients and nests `patient { id, first_name, last_name }`. |

## Behavior Notes

### Uploads

- The extension **or** the content type must match (`.txt`/`text/plain`, `.pdf`/`application/pdf`, `.csv`/`text/csv`).
- Text is extracted into `raw_text` (UTF-8 decode, or `pypdf` for PDFs) and must be non-empty. PDFs must have extractable text.
- The original bytes are stored in the configured backend (`STORAGE_BACKEND=local|s3`). The storage key is never exposed, and downloads stream through the API rather than redirecting to S3.
- A `503` means the storage backend is unreachable. Validation runs first, so bad files never reach storage.
- AI analysis only reads `raw_text` from Postgres and never touches storage.

### Two different CSV endpoints

- `/medications/import` parses rows into `Medication` records.
- `/clinical-documents/upload-csv` stores raw text as AI evidence and does no row validation.

They are unrelated. Uploading the same file to both is legitimate.

### Medication CSV import

- Required headers: `medication_name, dose, route, frequency, status, source`. `notes` is optional.
- Headers are case-insensitive and trimmed. Extra columns are ignored, and fully blank rows are skipped.
- **Atomic:** if any row fails, nothing is created. The 422 lists every bad row, numbered from 2 because the header is row 1:

```json
{ "detail": { "message": "CSV import failed validation. No medications were created.",
              "row_errors": [{ "row": 3, "errors": [{ "field": "dose", "message": "..." }] }] } }
```

- Success returns `{ rows_processed, medications_created, blank_rows_ignored }`.

### Analysis creation

- Every document id must belong to the patient; otherwise the request returns `404` and nothing is created.
- Documents can be new uploads or ones already on file. The endpoint doesn't distinguish.
- Reconciliation runs in the same request and its findings are persisted. They appear in the detail response, not in the POST response.
- If the AI provider fails, the analysis is marked `failed` with a sanitized `error_message` and the request returns `503`. No partial discrepancies are left behind.

### Analysis detail

- `medication_discrepancies` nest their evidence: a `medication_mention` (with `context_text` and a `clinical_document` citation without `raw_text`) and/or a `medication` (the full list row). Either can be `null` because both foreign keys are `ON DELETE SET NULL`.
- `open_findings` on summaries is computed live. `total_findings` and the severity counts are frozen when the analysis completes.

### Resolving a discrepancy

Body: `action` (`add_medication` | `update_medication` | `dismiss`), optional medication fields, and an optional `note`.

| `discrepancy_type` | Valid actions |
|---|---|
| `missing_from_medication_list` | `add_medication` (all 5 fields required; creates a Medication with `source: "reconciliation"`), `dismiss` |
| All others | `update_medication` (at least one field; updates the linked Medication), `dismiss` |

"Mark discontinued" and "mark active" are just `update_medication` with `status` set.

- `resolution_status` becomes `resolved` or `dismissed`, and the response includes the audit fields (`resolution_action`, `resolved_at`, `resolution_note`, `resolved_by`).
- The original finding fields never change.
- `400` means the action is invalid for this type. `409` means the discrepancy was already resolved; resolution is one-way.

## Error Format

Every error body has a `detail` key.

| Status | When |
|---|---|
| 400 | Only for an invalid resolve action |
| 401 | Bad login, or a missing, invalid, or expired token |
| 404 | Not found, or not yours |
| 409 | Duplicate email or username; discrepancy already resolved |
| 422 | Body validation (FastAPI's list format) or CSV row errors (object format above) |
| 503 | AI provider failure (missing key, timeout, invalid output) or storage unreachable |
