# Architecture

## Overview

MedLens follows a modern three-tier web architecture: a React frontend, a FastAPI backend, a PostgreSQL database, and an external AI provider (Google Gemini) integration, fronted in every real deployment by a single nginx reverse proxy.

The application is designed around a clinical documentation reconciliation workflow. Users upload multiple synthetic clinical documents, the backend orchestrates AI-powered medication extraction, and a deterministic reconciliation engine, a separate, non-AI component, compares that extracted information against a patient's medication list to identify potential documentation inconsistencies for a human to review.

This document is conceptual: it explains how the pieces fit together, why they're divided the way they are, and how a request actually flows through the system. It deliberately does not restate what's already documented in depth elsewhere; it links to that documentation instead:

- `docs/frontend.md`: frontend implementation detail (routing table, component organization, theming, accessibility, state management)
- `docs/api.md`: the full HTTP contract (every endpoint, request/response schema, error format)
- `docs/ai.md`: the AI layer's implementation detail (provider abstraction, prompt management, structured output, validation, testing)
- `docs/deployment.md`: operational deployment detail (environment variables, the AWS EC2 runbook, HTTPS setup, monitoring)
- `docs/testing.md`: testing philosophy, tooling, and conventions
- `docs/data-model.md`: the full entity/column reference
- `docs/design-decisions.md`: the reasoning behind specific choices, referenced by number throughout this document

---

## Architectural Goals

The architecture is designed to be:

- Modular
- Scalable
- Testable
- Maintainable
- Secure
- Production-ready
- Easily deployable with Docker
- Cloud-native

---

## Technology Stack

### Frontend

- React
- TypeScript
- Vite
- React Router

### Backend

- FastAPI
- SQLAlchemy
- Alembic
- Pydantic

### Database

- PostgreSQL

### AI

- Google Gemini API

### Infrastructure

- Docker / Docker Compose
- nginx (reverse proxy, TLS termination, static SPA serving; see Deployment below)
- Certbot / Let's Encrypt (HTTPS certificate issuance and renewal)
- GitHub Actions (CI)
- AWS EC2 (hosting)
- AWS S3 (optional file-storage backend, implemented, not planned; see Persistence below)

---

## High-Level Architecture

```text
                              User (browser)
                                    │
                                    ▼
                    nginx (frontend container)
              single public entry point - see Deployment
        ┌───────────────────────────┴───────────────────────────┐
        ▼                                                        ▼
serves the built React SPA                        reverse-proxies /api/* ──►  FastAPI Backend
(static files)                                     (internal-only, never reachable directly)
                                                                │
                                          ┌─────────────────────┼─────────────────────┐
                                          ▼                     ▼                     ▼
                                     PostgreSQL          Gemini API           Storage (local disk
                                  (internal-only)     (structured extraction)   or S3, pluggable)
                                                                │
                                                                ▼
                                                   Reconciliation Engine
                                                (deterministic, no AI - runs
                                                 inside the backend process)
```

Every arrow above is a real dependency direction, not just a data path: the backend depends on Postgres, Gemini, and the storage backend, but none of those depend back on it, and the reconciliation engine depends on nothing external at all (see Component Interaction, below).

---

## System Components

### Frontend

A React + TypeScript single-page application (Vite build), responsible for every user-facing interaction: authentication, patient management, clinical document upload (pasted text or file), starting and viewing AI analyses, reviewing and resolving medication discrepancies, and account/profile settings. It talks to the backend exclusively over HTTP through a single configured Axios client, and holds no business logic of its own beyond client-side form validation and presentation: every decision about what's valid, what's owned by whom, and what an AI response means is made by the backend.

See Frontend Architecture (below) for how routing, authentication, and API communication are structured, and `docs/frontend.md` for the full implementation reference (routing table, component organization, theming, accessibility).

### Backend

A FastAPI application responsible for authentication, every API endpoint, business logic (in a dedicated service layer, not in route handlers), AI orchestration, the deterministic reconciliation workflow, file storage orchestration, and all database communication. See Backend Architecture (below) for how routers/services/models/schemas are organized, and `docs/api.md` for the full endpoint reference.

### Database

PostgreSQL. Stores every persisted application resource: `User`, `Patient`, `ClinicalDocument`, `MedicationMention`, `Medication`, `Analysis`, `MedicationDiscrepancy`, `AnalysisMedicationMention`, and `AnalysisInconsistency`. It does **not** store uploaded files' original bytes; those go to the pluggable storage backend (local disk or S3), while Postgres stores each document's *extracted text* (`raw_text`) and file metadata only. See Persistence (below) and `docs/data-model.md` for the full entity reference.

### AI Service

Reads clinical note text and produces structured, validated output: which medications are mentioned, their stated dosage/route/frequency/status, a list of places notes appear to disagree with each other, and a short summary, nothing more. It is implemented behind a provider-abstraction interface (currently one implementation, Gemini) and never makes a clinical decision, never decides whether an extracted medication conflicts with anything, and is not involved in medication normalization or reconciliation at all; both of those are deterministic backend logic (see Reconciliation Engine, below, and `docs/ai.md`'s AI Philosophy section for the full AI-vs-deterministic boundary). See `docs/ai.md` for the complete implementation reference; this document does not duplicate it.

---

### Reconciliation Engine

Implemented as a deterministic backend service, not an AI component. Given a patient and a set of clinical documents, it:

- Validates that every selected document exists and belongs to that patient, reusing the same validation as analysis creation.
- Loads the patient's current Medication records and the MedicationMention records extracted from the selected documents.
- Normalizes medication names and comparable fields (dose, route, frequency, status) using fixed rules: trimming, lowercasing, whitespace collapsing, and a small set of explicit aliases such as PO to oral and QD to daily. No fuzzy matching, brand-to-generic inference, or semantic matching is performed.
- Applies a fixed set of comparison rules to produce MedicationDiscrepancy records, each with a deterministic title, explanation, expected value, and observed value.
- Assigns severity from a single, centralized mapping from discrepancy type to severity.

AI is responsible only for producing the medication data the reconciliation engine reads. The comparison logic itself never calls an AI provider, so its output is reproducible and directly testable (Decision 12, `docs/design-decisions.md`); see `docs/ai.md`'s Reconciliation Pipeline section for the full AI-decision-vs-deterministic-logic breakdown.

This engine is invoked automatically as part of analysis creation; see "Clinical Document Analysis" under Request Flow, below. `run_medication_reconciliation` (`app/services/medication_reconciliation_service.py`) remains a second, independent entry point into the same engine: given a patient and a set of clinical document ids, it creates its own Analysis, queries `MedicationMention` rows already persisted against those documents (rather than bridging AI-extracted ones), and completes or fails that Analysis on its own. Today, no API route calls it directly; the shared logic it always used (`build_discrepancy_findings`, `create_medication_discrepancies`, severity counting) was extracted into a `reconcile_medications` helper so the AI-summary flow could reuse the exact same engine rather than duplicating it.

**Resolution is a distinct, separate step from detection.** This engine only ever *detects* discrepancies; a provider actually reviewing, accepting, or dismissing one is additive functionality layered on the same `MedicationDiscrepancy` rows (`app/services/medication_discrepancy_service.py`), not a second pipeline: the engine itself has no notion of "resolved" and never re-runs to reflect one. Resolution is one-way (`open` → `resolved`/`dismissed`, never back) and always a deliberate human action through a dedicated endpoint, never automatic. See `docs/api.md`'s discrepancy-resolution endpoint documentation for the full request/response contract and the action-validity rules.

---

## Persistence

### PostgreSQL and SQLAlchemy

A single PostgreSQL database, accessed through SQLAlchemy's ORM. `app/db/session.py` defines one `Engine` and one `sessionmaker` (`SessionLocal`) for the whole process; `get_db()` is a FastAPI dependency that yields one `Session` per request and always closes it afterward (`try`/`finally`), regardless of whether the request succeeded. Every route that touches the database declares `db: Session = Depends(get_db)` rather than constructing a session itself, the same dependency-injection pattern used for authentication, AI, and storage (see Component Interaction, below).

### Alembic (schema migrations)

Schema changes are managed as versioned Alembic migrations under `backend/alembic/versions/`. Migrations are **not** a separate, manually-run deployment step: `backend/Dockerfile`'s container start command runs `alembic upgrade head` before starting `uvicorn`, on every container start (Decision 19, `docs/design-decisions.md`). A fresh database gets its schema automatically on first boot, and re-running against an already-current schema is a documented no-op. `backend/alembic/env.py` reads `DATABASE_URL` from the environment when present, so this resolves correctly whether running inside the container (Postgres reachable by its Compose service name) or directly on a developer's host (`localhost`). See `docs/deployment.md` for the operational detail (what a failed migration looks like, rollback procedure).

### Storage Abstraction

File persistence is a capability layered on top of an unchanged extraction pipeline: `upload-txt`/`upload-pdf`/`upload-csv` still read a file into memory and extract its text into `raw_text` exactly as before; the original bytes are additionally uploaded to a configured storage backend rather than discarded. See `docs/data-model.md`'s Design Decisions for the full "additive, not a migration" framing.

`StorageService` (`app/storage/base.py`) is an abstract interface with three methods, `upload(key, content, content_type)`, `download(key) -> StoredObject`, `delete(key)`, and two exceptions, `StorageError` (the operation failed) and `ObjectNotFoundError` (a `StorageError` subtype specifically for "no object at this key"). It is deliberately the same shape as `AIProvider` (`app/ai/providers/base.py`, see Decision 15 in `docs/design-decisions.md`): business logic depends only on the interface, never on a concrete backend, so which backend is active is a matter of configuration, not conditionals scattered through upload/download/delete code (Decision 21).

Two implementations exist:

- **`LocalStorageService`** (`app/storage/local.py`): writes objects as plain files under a local directory (`Settings.local_storage_dir`), with a small `<key>.meta.json` sidecar file recording the content type (a plain filesystem has no first-class concept of content type, unlike S3's object metadata). The default backend, zero AWS configuration needed, so local development, CI, and this feature's own test suite (`tests/test_clinical_documents.py`, `tests/test_clinical_document_service.py`) all work without touching AWS at all.
- **`S3StorageService`** (`app/storage/s3.py`): uploads/downloads/deletes objects in a single private S3 bucket via `boto3`. Every `put_object` call sets `ACL="private"` explicitly, defense in depth on top of the bucket itself being expected to block public access at the account level (see `docs/deployment.md`'s Security section: "never make uploaded files public" is enforced at both layers, not just one). Credentials are passed to `boto3` only when both `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are configured (for a developer testing against a real bucket locally); otherwise `boto3`'s own default credential chain is used, which includes an IAM role attached to the EC2 instance in production, the "use IAM credentials" requirement this feature specifically asked for.

**Selection** happens in exactly one place, `build_storage_service` (`app/storage/service.py`), branching on `Settings.storage_backend` ("local" or "s3"), the only conditional anywhere in the codebase that knows both backends exist. Routes and services depend on `get_storage_service` (a FastAPI dependency wrapping `build_storage_service`) and the abstract `StorageService` type only, the same dependency-injection pattern `get_ai_summary_service` already established for AI providers (`app/ai/service.py`).

**Configuration validation happens at startup, not on first use.** `Settings` (`app/core/config.py`) is constructed once, at module import time (`settings = Settings()`); a `model_validator` on it raises immediately if `storage_backend == "s3"` but `aws_region` or `s3_bucket_name` is missing, so a misconfigured deployment fails to start at all rather than coming up looking healthy and only breaking on the first upload request. `aws_access_key_id`/`aws_secret_access_key` are deliberately not required even when S3 is selected; see the IAM-role reasoning above.

**Key generation** (`_build_storage_key`, `app/services/clinical_document_service.py`) always includes a `uuid4` segment (`clinical-documents/{patient_id}/{uuid4()}/{filename}`), which is what actually guarantees "never overwrite an existing object": two uploads of the same filename, even for the same patient, get different keys. `storage_key` is never exposed over the API (`docs/api.md`) or stored as a URL (`docs/data-model.md`); only the fact that a document has a file (`file_size_bytes` not null) and the download endpoint that resolves it internally.

### Uploaded document lifecycle

1. **Upload**: the original file is uploaded to storage *before* the database row is created. If the subsequent `db.commit()` fails, the just-uploaded object is deleted best-effort (a secondary failure there is logged, not raised) before the original database error propagates, since otherwise a failed document creation would silently leak an orphaned object with nothing in Postgres ever pointing to it.
2. **Read**: `raw_text` (always in Postgres) is what AI analysis reads; the original file bytes are read only when a user explicitly downloads the document, streamed back through the backend (never a redirect to a bucket URL).
3. **Delete**: the database row is deleted *first*; the storage object is deleted second, and treated as non-fatal if it fails (caught and logged, not raised). This ordering is deliberate: deleting storage first and having the database delete fail afterward would leave a document that still exists but points at a file that's already gone (a real, user-visible inconsistency, since it appears in the list but 404s on download); deleting the database row first means the worst case of a subsequent storage failure is a harmless orphaned object in storage, a cleanup/cost concern, never something a user can observe as broken.

A document created from pasted text (no file uploaded) has no storage object at all: `file_size_bytes`/`content_type`/`storage_key` are all `null`, and the download endpoint 404s for it. See `docs/api.md`'s File Uploads section for the full request/response contract.

---

## Frontend Architecture

The frontend is organized into `pages/` (route-level components), `components/` (shared and layout-specific UI), `hooks/` (data-fetching and shared stateful logic), `contexts/` (React Context providers), `api/` (the single Axios client), `layouts/` (route-group shells like `AppLayout`), and `lib/`/`utils/` (small framework-adjacent helpers). See `docs/frontend.md`'s Folder Structure section for the full layout; this document only summarizes the pieces relevant to how the frontend fits into the system as a whole.

- **Routing.** `App.tsx` composes the app's providers (`ThemeProvider` → `BrowserRouter` → `AuthProvider`) around `AppRoutes`, which declares every route with `react-router-dom`'s declarative `<Routes>` API (not the data-router/loader API). Protected routes are wrapped in `ProtectedRoute`, which redirects to `/login` when there is no authenticated user. See `docs/frontend.md`'s Routing section for the full route table.
- **Authentication.** `AuthContext`/`AuthProvider` hold the current user, token, and derived `isAuthenticated` state; the token is persisted to `localStorage` and restored (and re-validated against `GET /users/me`) on load. A background `401` (an expired or revoked token) triggers a silent logout with a user-visible explanation on the next login attempt, via a handler registered on the API client. See Authentication (below) for the backend side of this, and `docs/frontend.md`'s Authentication Foundation section for the frontend implementation.
- **API client.** `src/api/client.ts` exports a single configured Axios instance used for every backend request; a response interceptor (`toApiError`) normalizes every failure shape the backend can return (a plain string `detail`, a list of field errors, the CSV importer's structured row errors, or no response at all) into one consistent `ApiError`. This is the frontend's one boundary with the backend; no component or hook talks to Axios directly.
- **State management.** Global state uses React Context only (`AuthContext`, `ThemeProvider`); there is no Redux or other external state library. Per-page server state (patients, documents, analyses, ...) is fetched and cached locally by dedicated hooks (e.g. `usePatients`, `useAnalysisPolling`), not lifted into global state, since nothing in the application needs the same server data shared across unrelated parts of the page tree at once.
- **Component organization.** Route-level pages live in `pages/`; presentational pieces reused across pages live in `components/common/`; feature-specific pieces (patient breadcrumbs, medication cards, discrepancy resolution UI) live in their own `components/<feature>/` subfolder alongside the page(s) that use them.

---

## Backend Architecture

The backend follows a layered, service-oriented structure (Decision 7, `docs/design-decisions.md`): `app/api/routes/` (HTTP-facing routers), `app/services/` (business logic), `app/models/` (SQLAlchemy ORM models), `app/schemas/` (Pydantic request/response models), `app/core/` (configuration, security, logging), `app/db/` (the session layer, above), `app/ai/` (the provider-abstracted AI layer, `docs/ai.md`), and `app/storage/` (the provider-abstracted storage layer, above).

- **Routers** (`app/api/routes/*.py`) are grouped by resource (`auth`, `users`, `patients`, `medications`, `clinical_documents`, `analyses`, `health`), each an `APIRouter` included into the single `FastAPI` app in `app/main.py`. A router's job is to translate an HTTP request into a service call and a service result into an HTTP response: request/response validation is delegated entirely to Pydantic schemas declared as parameter and `response_model` types, and business logic is delegated entirely to the service layer. The one deliberate exception (Decision 17) is `POST /patients/{patient_id}/analyses`, which orchestrates several service calls in sequence (create → mark processing → call AI → persist/reconcile) and owns the transaction's rollback-on-failure logic itself, rather than that sequencing living in a service function nothing else would reuse.
- **Services** (`app/services/*.py`) hold business logic and are the only layer that queries or mutates the database directly (aside from the dependency-injected `db: Session` itself). Each service module is scoped to one resource or concern (`patient_service`, `medication_service`, `analysis_service`, `medication_reconciliation_service`, ...) and depends only on models and schemas, never on `app/api/routes/`, so nothing in this layer needs to know it's being called from an HTTP request at all (it's exactly as testable called directly from a test as from a route).
- **Models** (`app/models/*.py`) are plain SQLAlchemy ORM classes, one per table, with relationships declared for the associations described in Data Model (below). They carry no validation logic of their own; validation is Pydantic's job (see Schemas, next).
- **Schemas** (`app/schemas/*.py`) are Pydantic models used two ways: as FastAPI request bodies (validated automatically before a route handler ever runs) and as `response_model`s (guaranteeing a route can only return the shape it declares). See `docs/api.md` for the full schema reference and examples.
- **Dependency injection.** FastAPI's `Depends()` is the one mechanism used throughout for every cross-cutting concern: `get_db` (a database session), `get_current_user`/`get_owned_patient` (authentication and ownership; see Authentication, below), `get_ai_summary_service` (the AI provider), and `get_storage_service` (the storage backend). All four follow the identical pattern, a plain factory function, injected rather than imported and constructed inline, which is also the seam every layer of testing uses to substitute a fake (`docs/testing.md`).

See `docs/api.md` for the complete endpoint reference this architecture serves.

---

## Logging

The backend uses one centrally-configured structured logging system, without needing to change any of the standard-library `logging.getLogger(__name__)` calls scattered throughout the codebase (Decision 22, `docs/design-decisions.md`).

**`app/core/logging_config.py`** is the single place that ever touches handler/formatter setup: `configure_logging(app_env, log_level)` is called once, at import time in `app/main.py`, before anything else runs. It installs one `StreamHandler` on the *root* logger (so every `logging.getLogger(__name__)` call anywhere in the process, application code and any third-party library alike, shares the same handler and format), and selects between two formatters based on `Settings.app_env`:

- **`ConsoleFormatter`** (development): one readable `key=value` line per record, for a developer's terminal.
- **`JSONFormatter`** (everywhere else, including production): one JSON object per line, suited to `docker compose logs` piped through `jq` or a log aggregator.

Both formatters draw from the exact same allowlist, `ALLOWED_FIELDS`, a fixed, explicit tuple of field names (`event`, `request_id`, `method`, `path`, `status_code`, `duration_ms`, `client_ip`, `user_id`, `patient_id`, `analysis_id`, `document_id`, `file_type`, `provider`, `model`, `error_type`, `storage_key`, `version`, `environment`, `storage_backend`). This is a deliberate security boundary, not just documentation: a field passed via `extra={...}` at some call site that isn't in this tuple is silently dropped by both formatters, so a mistaken `extra={"password": ...}` anywhere in the codebase can never actually reach a log line without also being added to this one, visible, reviewable list first. Credentials, JWTs, Authorization headers, Gemini prompts, and clinical document/file content are never passed via `extra=` anywhere in the codebase in the first place; the allowlist is defense in depth on top of that, not a substitute for it.

**Request-scoped context** (`request_id`, `method`, `path`, `client_ip`) is carried by a `contextvars.ContextVar`, set once by the request-logging middleware (below) and read automatically by every log call during that request via `RequestContextFilter`, a `logging.Filter` installed on the one handler `configure_logging` creates. `user_id` is deliberately **not** carried this way: every dependency and route handler in this codebase is a synchronous `def` (SQLAlchemy is used synchronously throughout), and Starlette runs each sync callable via `run_in_threadpool`, which executes it inside its own *copy* of the current context (`contextvars.copy_context().run(...)`), so a `ContextVar.set()` made inside one sync dependency is invisible to a sibling sync dependency or to the middleware's own code, even on the same request. `user_id` instead rides `request.state` (a plain mutable attribute on the one `Request` object every dependency and the middleware share, not subject to the same per-call context-copy isolation): `get_current_user` (`app/api/deps.py`) sets `request.state.user_id` once a JWT resolves to a real user, via `set_request_user_id` (`app/core/logging_config.py`), and the request-logging middleware reads it back from `request.state` after `call_next()` returns to include in its own summary line. Individual route logs that already have the user object in scope (e.g. login/registration) pass `user_id` explicitly via `extra=` instead, unaffected by any of this.

**`configure_request_logging(app)`** registers one `@app.middleware("http")` responsible for the "exactly one request summary per completed request" requirement: it times the request, generates a `request_id` (a `uuid4`), logs one `http_request_completed` line after `call_next()` returns (with `status_code`, `duration_ms`, and `user_id` from `request.state`), and sets an `X-Request-ID` response header for end-to-end tracing. `/health` is excluded (Docker's own healthcheck polls it every 10s, pure log noise, never a signal an operator would want). Uvicorn's own default access log is disabled via `--no-access-log` (see the Dockerfile's `CMD` and `docs/deployment.md`) so this is the *only* per-request log line, not a second differently-formatted one alongside it.

**`configure_exception_handling(app)`** registers a handler for the bare `Exception` type. FastAPI's own, higher-priority handler for `HTTPException` is untouched, so every existing `raise HTTPException(...)` throughout the app keeps producing exactly the response it already did. This handler only ever fires for a genuinely unexpected exception (a bug, not a deliberate application response): it logs the full exception with a server-side traceback (`unhandled_exception`) and returns a generic `{"detail": "Internal server error"}` 500 response; the client never sees the exception's message, type, or traceback.

**Lifecycle events** logged elsewhere in the codebase using this same structured format: application startup/shutdown (`app/main.py`'s `lifespan`), login success/failure and registration (`app/api/routes/auth.py`), document upload/deletion (`app/services/clinical_document_service.py`), analysis started/completed/failed (`app/api/routes/analyses.py`), Gemini request success/failure and AI response validation failure (`docs/ai.md`'s Error Handling section), and S3 upload/download/delete failure (`app/storage/s3.py`, only for genuine operational failures, never for an expected `ObjectNotFoundError`, an already-handled condition). Alembic's own migration logging (`alembic.ini`) is a pre-existing, separate subsystem, left untouched rather than unified into this format.

---

## Authentication

Authentication uses JSON Web Tokens (JWT), issued by `POST /auth/login` and required as a `Authorization: Bearer <token>` header on every protected endpoint; see `docs/api.md`'s Authentication and Authentication Flow sections for the full HTTP-level contract (this section covers only how it's implemented, not the request/response shapes).

- **Token handling** (`app/core/security.py`): `create_access_token`/`decode_access_token` wrap `PyJWT`, signing with `Settings.jwt_secret_key`/`jwt_algorithm` and a fixed expiry (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, default 30). The token's only payload is the user's id (`sub` claim); no role, permission, or other claim exists, since every authorization decision in this application reduces to "does this resource belong to this user" (see Ownership model, below), not a role check.
- **Request authentication** (`app/api/deps.py`): `get_current_user` is a FastAPI dependency built on `OAuth2PasswordBearer` (which extracts the bearer token from the `Authorization` header): it decodes the token, loads the referenced `User` by id, and raises `401` if the token is missing, malformed, expired, or references a user that no longer exists. Every protected route declares `current_user: User = Depends(get_current_user)` (directly, or transitively through `get_owned_patient` below) rather than reading the header itself.
- **Ownership model.** Every clinical resource (`Patient`, and everything nested under it: `Medication`, `ClinicalDocument`, `Analysis`) is scoped to the authenticated user, directly (`Patient.user_id`) or transitively (`patient_id`). `get_owned_patient` (`app/api/deps.py`) is the one shared dependency every patient-nested route uses to resolve `patient_id` from the URL and enforce ownership in a single place, rather than each route re-implementing the same check. A resource that exists but belongs to someone else is deliberately indistinguishable from one that doesn't exist at all: both return `404`, never `403`, so a caller can't use this API to probe for the existence of another user's data.
- **Password storage**: `bcrypt` via `passlib`, never plain text or a reversible encoding; verified, never decrypted, at login.

---

## Deployment

This is a conceptual summary of the deployment topology; `docs/deployment.md` is the authoritative operational reference (every environment variable, the full AWS EC2 runbook, HTTPS setup and renewal, rollback, monitoring).

Four Docker Compose services make up a deployment (local or production; the same `infra/docker-compose.yml` runs both, no separate production configuration):

- **`frontend`**: an nginx container serving the built React SPA and acting as the **single public entry point** (Decision 24, `docs/design-decisions.md`): it terminates HTTPS, serves the static frontend, and reverse-proxies `/api/*` to the `backend` service over the internal Docker network. This is what makes the browser's requests to the backend same-origin; there is no CORS configuration needed for a deployed frontend at all (CORS exists only for `npm run dev`'s standalone Vite dev server, which talks to the backend directly). A companion `certbot` service (only ever run on demand, never continuously) issues and renews the real Let's Encrypt certificate into a shared volume this container reads from; until one exists (a fresh install), a short-lived self-signed placeholder lets nginx bind to 443 immediately.
- **`backend`**: the FastAPI application (via `uvicorn`), published only on `127.0.0.1`, reachable from the host machine itself (for direct `curl`/debugging, or `npm run dev`), but never from outside it. In a real deployment, nginx is the only thing that can reach it at all.
- **`postgres`**: the database, published only on `127.0.0.1` for the same reason; nothing outside this Compose network ever needs to reach it directly.
- **`certbot`**: on-demand only (a Compose `profile`, not started by a normal `docker compose up`); shares the certificate volume with `frontend` and is the only thing that ever writes to it.

Health checks are wired for all three always-on services (`docker compose ps` reflects real readiness, not just "container started"), and `backend`/`postgres` restart automatically (`restart: unless-stopped`) if they crash. See `docs/deployment.md`'s Docker Strategy, Reverse Proxy, and HTTPS/TLS sections for the full detail behind each of these.

---

## Request Flow

Three representative flows, chosen to cover this application's three fundamentally different request shapes: one that never touches AI or storage (Login), one that touches storage but not AI (Document Upload), and the one that touches every layer (Clinical Document Analysis).

### Login

```text
Browser
   │  POST /auth/login  { email, password }
   ▼
Frontend (AuthProvider.login())
   │
   ▼
Backend  (app/api/routes/auth.py)
   │  authenticate_user(): looks up the user by email, verifies the
   │  bcrypt password hash
   ▼
Database  (User table)
   │
   ▼
Backend
   │  create_access_token(): signs a JWT containing the user's id
   ▼
Browser
      receives { access_token, token_type }, persists it (localStorage),
      and attaches it as `Authorization: Bearer <token>` on every
      subsequent request
```

No AI, storage, or reconciliation involvement: the simplest flow in the system, and the one every other authenticated flow below builds on.

### Document Upload

```text
Browser
   │  multipart/form-data: document_type, title, file
   ▼
Backend  (app/api/routes/clinical_documents.py)
   │  1. Validate file extension/content-type
   ▼
Text Extraction
   │  plain UTF-8 decode (.txt/.csv) or pypdf (.pdf)
   ▼
Storage  (local disk or S3, app/storage/)
   │  the *original file bytes* are uploaded here, before any
   │  database row exists
   ▼
Database  (ClinicalDocument row: raw_text + file metadata,
           storage_key never exposed to the client)
```

No AI involvement at all: extraction here means pulling raw text out of a file, not structured understanding of its contents. See Persistence's "Uploaded document lifecycle" (above) for what happens on read/delete afterward, and `docs/api.md`'s File Uploads section for the full endpoint contract.

### Clinical Document Analysis

```text
Browser
   │  POST /patients/{id}/analyses  { clinical_document_ids }
   ▼
Frontend
   ▼
Backend  (app/api/routes/analyses.py)
   │  1. Validate every document exists and belongs to this patient
   │  2. Mark Analysis "processing"
   ▼
AI  (AISummaryService → GeminiProvider, docs/ai.md)
   │  reads each document's already-stored raw_text, returns raw JSON
   ▼
Validation  (ClinicalSummary.model_validate_json(), extra="forbid")
   │  malformed JSON or a schema mismatch fails the analysis here,
   │  before anything is persisted
   ▼
Reconciliation  (deterministic, no AI; see Reconciliation Engine, above)
   │  AI-extracted medications are persisted as MedicationMention rows,
   │  then compared against the patient's actual Medication list
   ▼
Database
   │  MedicationDiscrepancy rows persisted, Analysis marked "completed"
   │  with real severity counts
   ▼
Frontend
      GET /patients/{id}/analyses/{analysis_id} renders the AI summary
      and reconciliation findings on the Analysis Results page
```

This is the one flow that touches every layer in the system, and the one place the AI/deterministic boundary (`docs/ai.md`'s AI Philosophy section) matters most operationally: a failure anywhere in the AI or Validation stage fails the whole analysis (marked `failed`, with a sanitized message; `docs/ai.md`'s Error Handling section) and reconciliation never runs; a failure in Reconciliation itself rolls back everything staged, including the `MedicationMention` rows the AI stage already produced, so a completed Analysis is never left with partial results. See `docs/ai.md`'s Data Flow section for the same flow narrated step-by-step from the AI layer's own point of view, and `docs/api.md` for the full request/response contract.

---

## Component Interaction

Dependency direction is one-way and layered: a lower layer never imports from a higher one:

```text
app/api/routes/   ──depends on──►   app/services/   ──depends on──►   app/models/
      │                                    │
      │                                    └──depends on──►  app/schemas/  (shapes, not logic)
      │
      └──depends on (via Depends())──►  app/ai/  and  app/storage/
                                         (through their abstract interfaces only -
                                          never a concrete provider/backend class)
```

- **Routers → services.** A router calls one or more service functions and translates the result (or a service-raised exception, e.g. `EmailAlreadyRegisteredError`, `InvalidResolutionActionError`) into an HTTP response and status code. Routers never construct a SQLAlchemy query directly.
- **Services → models.** Services are the only layer that queries/mutates the database, using models directly. A service never imports from `app/api/routes/`; this is what makes every service testable by calling it directly, with a real database session and no HTTP layer involved at all (`docs/testing.md`).
- **Routers/services → AI and storage.** Both are reached exclusively through FastAPI's dependency injection (`Depends(get_ai_summary_service)`, `Depends(get_storage_service)`), never imported and constructed inline in a router or service. This is what makes swapping the concrete implementation (a different AI provider, a different storage backend) a configuration change, not a code change anywhere that calls them (see Extension Points, below).
- **Authentication as a cross-cutting dependency.** `get_current_user`/`get_owned_patient` sit in front of nearly every route as a dependency, not as logic each route repeats: a router that needs an authenticated, owned `Patient` simply declares `patient: Patient = Depends(get_owned_patient)` and never touches the ownership check itself.
- **The reconciliation engine has no dependency on AI at all.** It's called *after* the AI layer's output has already been validated and persisted as plain `MedicationMention` rows, and its own module (`medication_reconciliation_service.py`) never imports `app/ai/providers/`. This is the one dependency that's deliberately *absent*, not present; see `docs/ai.md`'s Extending the AI Layer section for why that boundary is intentionally kept that way.

---

## Data Model

Every clinical resource is owned through `Patient`, not directly by `User`; see `docs/data-model.md` for the full entity reference and the ownership migration that got the schema here.

```text
User
 │
 └── Patient
        ├── ClinicalDocument
        │      └── MedicationMention
        ├── Medication
        └── Analysis
               ├── MedicationDiscrepancy
               ├── AnalysisMedicationMention
               └── AnalysisInconsistency
```

### Relationships

```text
User
 1 ─── many Patient

Patient
 1 ─── many ClinicalDocument

ClinicalDocument
 1 ─── many MedicationMention

Patient
 1 ─── many Medication

Patient
 1 ─── many Analysis

Analysis
 1 ─── many MedicationDiscrepancy

Analysis
 1 ─── many AnalysisMedicationMention

Analysis
 1 ─── many AnalysisInconsistency

Analysis
 many ─── many ClinicalDocument
```

---

## Security Considerations

The application includes:

- JWT authentication, with password hashing via `bcrypt` (never plain text or a reversible encoding).
- Every clinical resource scoped to its owning user, directly or transitively; see Authentication's Ownership model, above.
- HTTPS in every real deployment (Decision 25, `docs/design-decisions.md`): nginx terminates TLS, using a real Let's Encrypt certificate once issued, or a short-lived self-signed placeholder until then so the service is never left unencrypted by default. See Deployment, above, and `docs/deployment.md`'s HTTPS/TLS section.
- Network isolation: the backend and database are published only on `127.0.0.1` (see Deployment, above); nginx is the only thing that can reach either from outside the host in a real deployment.
- Environment variables for every secret (`JWT_SECRET_KEY`, `GEMINI_API_KEY`, database credentials, AWS credentials): never hardcoded, never committed.
- Input validation via Pydantic on every request body, and strict (`extra="forbid"`) schema validation on every AI response before it's trusted (`docs/ai.md`).
- Structured logging with a field allowlist (Logging, above): credentials, tokens, prompts, and clinical document content are never logged.
- Private-only file storage: uploaded documents are never made public; every object is uploaded with an explicit private ACL, the API only ever streams file bytes through the backend itself (never a bucket URL), and production credentials are expected to come from an IAM role rather than long-lived access keys; see the Storage Abstraction section above and `docs/deployment.md`.
- Non-root Docker containers (Decision 18, `docs/design-decisions.md`): the backend runs as a dedicated non-root user; neither image bundles build tooling, dev dependencies, or `.env` files (`.dockerignore`).

Only synthetic clinical data is used throughout the application.

---

## Future Architecture Improvements

Potential future additions include:

- Background processing using Celery or FastAPI Background Tasks
- Redis caching
- CloudWatch logging
- Kubernetes deployment
- Distributed tracing
- Sentry monitoring
- FHIR integration
- RxNorm integration

---

## Architectural Principles

Principles actually reflected in the current implementation, not aspirational ones:

- **Separation of concerns.** Routers, services, models, and schemas each have one job (Decision 7); see Backend Architecture, above.
- **Dependency inversion, where used.** Business logic depends on the abstract `AIProvider`/`StorageService` interfaces, never on a concrete provider or backend (Decisions 15, 21); the dependent code (`AISummaryService`, document/analysis routes) has no idea which implementation is actually running.
- **Deterministic business logic.** Medication reconciliation is explicit, testable, non-AI logic (Decision 12): the one place in the system where a wrong answer would be hardest to catch is deliberately not left to a language model.
- **Provider abstractions.** The same interface-plus-factory pattern is used twice, independently, for two genuinely different concerns (AI providers, storage backends), not because one copied the other's code, but because both are "swap an external dependency without touching the code that uses it" problems with the same shape.
- **Layered architecture.** A strict one-way dependency direction (routes → services → models); see Component Interaction, above.
- **Testability.** Every external dependency (the database, the AI provider, the storage backend) is reached through a seam, a FastAPI dependency, an abstract interface, that a test can substitute with a fake, without a live network call anywhere in the test suite (`docs/testing.md`).
- **Explicit validation.** Every request body is validated by Pydantic before a route handler runs; every AI response is validated against a strict schema before it's trusted; nothing is passed through unchecked on the assumption that "it should already be fine."
- **Modularity.** Each domain concern (patients, medications, clinical documents, analyses, discrepancy resolution) has its own router, service module, and schema module; adding a new one doesn't require touching an unrelated one.
- **AI as a component, not the product.** Clinical documents are the primary source of information; AI extracts structured data from them but never makes a clinical decision, and every AI-generated discrepancy carries supporting evidence from the original documentation so a human reviewer can verify it, not just trust it. Users remain responsible for reviewing and resolving every identified discrepancy; resolution is a deliberate, human, one-way action (see Reconciliation Engine, above), never automatic.

---

## Extension Points

Where the existing abstractions already make future growth possible without redesigning anything:

- **AI providers.** Implement `AIProvider` (`app/ai/providers/base.py`) and wire it into `get_ai_summary_service()` (`app/ai/service.py`). No change needed anywhere else: not the prompt template, not the API route, not the reconciliation engine. See `docs/ai.md`'s Extending the AI Layer section for the exact steps.
- **Storage providers.** Implement `StorageService` (`app/storage/base.py`) and wire it into `build_storage_service()` (`app/storage/service.py`), the identical pattern to AI providers, above (Decision 21).
- **API routes.** A new resource gets its own router module under `app/api/routes/`, included in `app/main.py`, with business logic in its own new service module (not folded into an existing one), following the same one-router-per-resource, one-service-per-concern shape every existing route already uses.
- **Frontend pages.** A new route-level page under `frontend/src/pages/`, registered in `src/routes/AppRoutes.tsx`, wrapped in `ProtectedRoute` if it requires authentication; see `docs/frontend.md`'s Routing section for the existing table to follow the same conventions from.
- **Services.** New business logic gets its own module under `app/services/`, scoped to one resource or concern, depending only on models and schemas, never on `app/api/routes/` (see Component Interaction, above), so it stays callable and testable independent of any specific route.

What is **not** an existing extension point, stated explicitly so it isn't assumed to be one: there is no plug-in system, no runtime provider selection (switching providers means editing the one factory function, not flipping an environment variable; `docs/ai.md`'s Configuration section), and the reconciliation engine is deliberately not designed to be swappable the way AI providers and storage backends are. It is meant to stay deterministic, full stop, not to gain a second implementation.
