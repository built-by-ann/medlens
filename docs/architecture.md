# Architecture

MedLens is a React SPA and a FastAPI backend backed by PostgreSQL, with nginx in front. Users upload synthetic clinical documents. AI extracts the medications they mention, and a **deterministic** reconciliation engine compares those against the patient's medication list to flag inconsistencies for a human to review.

This doc explains how the pieces fit together. Details live in [frontend.md](frontend.md), [api.md](api.md), [ai.md](ai.md), [data-model.md](data-model.md), [deployment.md](deployment.md), [testing.md](testing.md), and [design-decisions.md](design-decisions.md).

```text
                       Browser
                          │
                          ▼
              nginx (frontend container)
         ┌────────────────┴────────────────┐
         ▼                                 ▼
   static React SPA              /api/* ──▶ FastAPI backend (internal only)
                                            │
                     ┌──────────────────────┼──────────────────────┐
                     ▼                      ▼                      ▼
                PostgreSQL         AI provider (Gemini,     Storage (local or S3)
                                   or local Ollama)
                                            │
                                            ▼
                              Reconciliation engine
                              (deterministic, in-process)
```

## Stack

| Layer | Tech |
|---|---|
| Frontend | React, TypeScript, Vite, React Router, Tailwind |
| Backend | FastAPI, SQLAlchemy, Alembic, Pydantic |
| Database | PostgreSQL 16 |
| AI | Gemini (default), or OpenBioLLM and MedGemma via Ollama |
| Infra | Docker Compose, nginx, Certbot, GitHub Actions, AWS EC2, S3 |

## Backend Layout

```text
app/
  api/routes/   HTTP routers, one per resource
  services/     Business logic (the only layer that touches the DB)
  models/       SQLAlchemy models
  schemas/      Pydantic request/response models
  ai/           Provider-abstracted AI layer
  storage/      Provider-abstracted file storage
  core/         Config, security, logging
  db/           Engine and session
```

Dependencies only point one way: routes → services → models/schemas. Routes reach AI and storage only through `Depends()` on their abstract interfaces.

- **Routers** translate HTTP to service calls and never build queries. The one exception is `POST /patients/{id}/analyses`, which orchestrates several services and owns rollback (Decision 17).
- **Services** are scoped to one concern and never import routes, so they're testable by calling them directly.
- **Dependency injection** handles every cross-cutting concern: `get_db`, `get_current_user`, `get_owned_patient`, `get_ai_summary_service`, `get_storage_service`. These are also the seams tests use to swap in fakes.

## Authentication

- JWT (PyJWT) with only `sub` = user id and a 30-minute expiry. There is no session store.
- Passwords are hashed with bcrypt.
- Authorization is ownership-based. `get_owned_patient` resolves `patient_id` and enforces `Patient.user_id == current_user.id`. A resource that isn't yours returns 404, not 403 (Decision 26).

## Reconciliation Engine

Plain code in `medication_reconciliation_service.py` that never imports the AI layer (Decision 12). It:

1. Loads the patient's `Medication` rows and the `MedicationMention` rows from the selected documents.
2. Normalizes names and fields (trim, lowercase, collapse whitespace, explicit aliases such as `PO → oral` and `QD → daily`). There is no fuzzy or brand-to-generic matching.
3. Applies fixed rules to produce `MedicationDiscrepancy` rows, with severity from one central mapping.

Detection and resolution are separate. The engine only detects. A provider resolves or dismisses each finding through a dedicated endpoint, and resolution is one-way and always manual.

## Analysis Request Flow

```text
POST /patients/{id}/analyses { clinical_document_ids }
  1. Verify every document belongs to the patient
  2. Commit Analysis as pending, then as processing         (Decision 14)
  3. AISummaryService → provider, using each document's raw_text
  4. ClinicalSummary.model_validate_json (extra="forbid")
  5. Persist mentions → reconcile → persist discrepancies
  6. Commit as completed (or roll back steps 5 and 6, mark failed)
```

A failure in steps 3 or 4 marks the analysis `failed` with a sanitized message, and reconciliation never runs. A failure in step 5 rolls back everything staged in that step, so a completed analysis never has partial findings.

## File Storage

`StorageService` (upload, download, delete) has `Local` and `S3` implementations selected by `STORAGE_BACKEND` in a single factory (Decision 21). S3 configuration is validated at startup.

- **Upload:** extract `raw_text` → upload the original bytes → create the DB row. If the DB commit fails, the uploaded object is deleted on a best-effort basis.
- **Read:** AI only ever reads `raw_text` from Postgres. Original bytes are streamed through the API on download, never via a bucket URL.
- **Delete:** delete the DB row first, then the object (best-effort). The worst case is an orphaned object rather than a document that 404s on download.
- Keys are `clinical-documents/{patient_id}/{uuid4}/{filename}`, are never exposed, and never overwrite each other.
- S3 objects are uploaded with `ACL="private"`. Production credentials come from an instance IAM role.

## Logging

`app/core/logging_config.py` configures the root logger once (Decision 22).

- Development logs readable lines; everything else logs JSON.
- Only fields in `ALLOWED_FIELDS` are rendered.
- Middleware logs one `http_request_completed` line per request (skipping `/health`) and sets `X-Request-ID`. Uvicorn's access log is disabled.
- `request_id`, `method`, `path`, and `client_ip` travel in a ContextVar. `user_id` uses `request.state` because sync dependencies run in copied contexts.
- Unhandled exceptions are logged with a traceback and return a generic 500.

## Deployment Topology

The same Compose file runs everywhere (details in [deployment.md](deployment.md)):

- **frontend** (nginx): the only public entry point. It terminates TLS, serves the SPA, and proxies `/api/*`.
- **backend** and **postgres**: bound to `127.0.0.1` only.
- **certbot**: runs on demand to issue and renew certificates.

## Data Model

```text
User 1─* Patient
Patient 1─* ClinicalDocument 1─* MedicationMention
Patient 1─* Medication
Patient 1─* Analysis 1─* MedicationDiscrepancy
                     1─* AnalysisMedicationMention
                     1─* AnalysisInconsistency
Analysis *─* ClinicalDocument
```

See [data-model.md](data-model.md).

## Extension Points

- **AI provider:** implement `AIProvider` and register it in `get_ai_summary_service()` and the `AI_PROVIDER` setting. See [ai.md](ai.md).
- **Storage backend:** implement `StorageService` and register it in `build_storage_service()`.
- **New resource:** add its own router, service, and schema modules.
- **New page:** add it under `frontend/src/pages/`, register it in `App.tsx`, and wrap it in `ProtectedRoute`.

The reconciliation engine is deliberately **not** pluggable. It stays deterministic.

## Future

Background jobs (Celery), Redis, CloudWatch and Sentry, distributed tracing, and FHIR or RxNorm integration.
