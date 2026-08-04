# Design Decisions

## Overview

This document records significant architectural and technical decisions made during the development of MedLens. As the project evolves, new decisions and trade-offs will be documented here.

---

# Decision 1: FastAPI instead of Flask

**Decision**

Use FastAPI as the backend framework.

**Reasoning**

FastAPI provides automatic request validation, OpenAPI documentation, strong typing through Pydantic, and excellent performance. It is well-suited for modern REST APIs and AI applications.

**Trade-offs**

Pros

- Automatic API documentation
- Built-in request validation
- Excellent async support
- Strong type safety

Cons

- Smaller ecosystem than Flask
- Slight learning curve

---

# Decision 2: PostgreSQL instead of MongoDB

**Decision**

Use PostgreSQL as the primary database.

**Reasoning**

The application's data is highly relational. Users own notes, medications, analyses, and medication flags, making a relational database a natural fit.

**Trade-offs**

Pros

- Strong schema enforcement
- ACID compliance
- Excellent relational querying
- Mature ecosystem

Cons

- Less flexible than document databases
- Requires schema migrations

---

# Decision 3: React + TypeScript

**Decision**

Use React with TypeScript for the frontend.

**Reasoning**

TypeScript improves maintainability by catching errors at compile time and providing stronger editor support. React offers a component-based architecture suitable for scalable frontend development.

---

# Decision 4: Docker for Development

**Decision**

Containerize the application using Docker and Docker Compose.

**Reasoning**

Docker provides consistent development environments across machines and simplifies deployment.

Benefits include:

- Reproducible environments
- Easier onboarding
- Simplified deployment
- Isolated dependencies

---

# Decision 5: Structured AI Responses

**Decision**

Require the AI model to return structured JSON rather than free-form text.

**Reasoning**

Structured responses can be validated, tested, and safely integrated into downstream application logic.

Instead of:

- Long paragraphs

Return:

- Summary
- Conditions
- Medications
- Follow-up actions

This improves reliability and reduces parsing errors.

---

# Decision 6: Validate AI Output with Pydantic

**Decision**

Treat AI responses as untrusted input.

**Reasoning**

Large language models can return malformed or unexpected responses. Every AI response should be validated before being stored or displayed.

---

# Decision 7: Service-Oriented Backend

**Decision**

Separate API routes from business logic.

**Reasoning**

Routes should primarily handle HTTP requests and responses, while business logic belongs in dedicated service modules.

Example:

- Authentication Service
- AI Service
- Medication Service
- Analysis Service

Benefits:

- Easier testing
- Better organization
- Improved maintainability

---

# Decision 8: Synthetic Data Only

**Decision**

Use only synthetic clinical notes and medication lists.

**Reasoning**

The project is intended as a portfolio application and should not process real patient information.

Benefits:

- No HIPAA concerns
- Easier sharing and deployment
- Safe public demonstrations

---

# Decision 9: Agile Project Management

**Decision**

Manage development using GitHub Issues, Milestones, Project Boards, feature branches, and pull requests.

**Reasoning**

The goal is to simulate a professional software engineering workflow rather than simply producing working code.

---

# Decision 10: Database-Level ON DELETE SET NULL for Reconciliation Findings

**Decision**

Use `ON DELETE SET NULL` on the foreign keys from MedicationDiscrepancy to Medication and to MedicationMention, enforced at the database level.

**Reasoning**

Every other foreign key in the schema relies only on ORM-level cascade behavior, not a database-level `ON DELETE` action. MedicationDiscrepancy is a deliberate exception, because a reconciliation finding is a record of something that was true at analysis time. If the referenced Medication or MedicationMention is later deleted, the finding should survive with the reference cleared rather than being deleted along with it, and the referenced Medication or MedicationMention should never be deleted as a side effect of removing a finding.

**Trade-offs**

Pros

- Findings are not silently lost when a medication or mention is later removed
- A user's medication records and clinical evidence cannot be deleted as a side effect of finding cleanup
- Enforced at the database level, not only through application code

Cons

- Introduces a schema convention that differs from every other foreign key in the project
- Requires readers of the schema to understand why this table is treated differently

---

# Decision 11: Association Table for Analysis and ClinicalDocument

**Decision**

Represent the relationship between Analysis and ClinicalDocument with a dedicated association table, analysis_clinical_documents, using a composite primary key and `ON DELETE CASCADE` on both foreign keys, rather than a foreign key on either model.

**Reasoning**

An analysis can cover more than one clinical document, and the same document can be included in more than one analysis. A foreign key on Analysis or on ClinicalDocument can only represent a single direction of that relationship, so a true many to many association requires its own table. Unlike MedicationDiscrepancy's references, an association row carries no meaning of its own beyond linking one analysis to one document, so there is nothing to preserve if either side is deleted. `ON DELETE CASCADE` removes the link automatically, while leaving the analysis, its other documents, and its findings intact, and leaving the document and its other analyses intact.

The table uses a composite primary key of analysis_id and clinical_document_id instead of a surrogate id column, which is a deliberate exception to this project's usual pattern of giving every table a surrogate id. The composite key already uniquely identifies each link, and the table has no other attributes that would need a single id to reference.

**Trade-offs**

Pros

- Correctly represents a many to many relationship without duplicating document content or creating a second document table
- Link rows are cleaned up automatically, at the database level, when either side is deleted
- Composite primary key avoids an unused surrogate id on a table with no independent attributes

Cons

- First table in the project without a surrogate id column, which differs from the rest of the schema
- Adds a table whose sole purpose is linking, which the reconciliation service must join through when loading an analysis's documents

---

# Decision 12: Deterministic Reconciliation Without AI or Fuzzy Matching

**Decision**

Implement medication reconciliation as explicit, deterministic backend logic. Medication names and fields are compared using fixed normalization rules and a small, explicit alias list. No fuzzy matching library, vector search, or LLM call is used anywhere in the comparison itself.

**Reasoning**

AI is responsible for producing MedicationMention records from clinical text. Deciding whether two already-structured records conflict is a comparison problem, not an extraction problem, and does not need a language model. A deterministic implementation is reproducible, directly unit testable, and does not risk inventing brand or generic equivalence, correcting misspellings, or merging medications on partial string similarity, all of which could silently hide a real documentation inconsistency instead of surfacing it.

**Trade-offs**

Pros

- Fully reproducible and unit testable without any external service
- Cannot silently merge genuinely different medications
- No dependency on an AI provider being available or affordable at analysis time

Cons

- Will not catch a conflict where a document uses a materially different name for the same medication, such as a brand name where the list uses a generic name
- Requires new aliases to be added explicitly as they are identified, rather than inferred automatically

---

# Decision 13: Narrow Assumption for the Unsupported Medication List Entry Rule

**Decision**

Only generate an unsupported_medication_list_entry finding when at least one of the documents selected for the analysis has a document_type of medication_list or medication_reconciliation_form.

**Reasoning**

This finding type asserts that a medication in the user's list is not supported by the selected documents. That assertion is only safe if the selected documents can reasonably be expected to mention every current medication. A visit note, progress note, or discharge summary is not expected to re-list every medication a patient takes, so its silence proves nothing. A medication list or medication reconciliation form is different: both document types exist specifically to represent the current medication list, so silence there is meaningful evidence. Restricting the rule this way avoids the false positives the underlying finding type is most at risk of producing.

**Trade-offs**

Pros

- Avoids flagging medications as unsupported based on documents that were never meant to be exhaustive
- Uses a signal, document_type, that already exists rather than inventing a new one

Cons

- The rule produces no findings at all for an analysis that only includes visit notes or similar documents, even if a medication genuinely appears nowhere else
- Depends on document_type being set accurately at upload time

---

# Decision 14: Two-Phase Commit Boundary for Reconciliation Runs

**Decision**

Commit an Analysis in two separate steps before its findings exist: first as pending, then as processing. Only the remaining work, discrepancy creation and the final completed or failed transition, is committed as one atomic unit.

**Reasoning**

The existing Analysis service already commits each status transition independently. A single all-encompassing transaction across the entire reconciliation run would mean that if reconciliation fails, there would be no Analysis row at all to mark as failed, since the transaction that created it would also roll back. Committing pending and processing durably first guarantees a record of the run exists no matter what happens afterward, while still keeping discrepancy creation and the completion or failure fields atomic with each other, so no completed analysis can exist with a mismatched or missing set of findings.

**Trade-offs**

Pros

- A failed reconciliation run always leaves a durable, explained record instead of no record at all
- No completed analysis can exist with partially created discrepancies or counts that do not match them
- Reuses the existing single-item commit functions rather than introducing a new transaction pattern

Cons

- Not a single database transaction for the entire run, so an external observer could see a processing analysis with no findings yet
- Relies on rollback correctly discarding any discrepancies staged before a late failure, which must be verified by test rather than guaranteed by a single wrapping transaction

---

# Decision 15: Provider Abstraction for AI Integration

**Decision**

Define an abstract `AIProvider` interface with a single method, `generate_summary(prompt: str) -> str`, and one exception type, `AIProviderError`, that every provider raises for any failure. `AISummaryService` depends only on this interface. The first implementation, `GeminiProvider`, is the only concrete class that imports the Gemini SDK.

**Reasoning**

The project intends to evaluate multiple providers, including OpenAI, MedGemma, and OpenBioLLM. If business logic called a specific SDK directly, adding or swapping a provider would mean changing the service layer itself. Behind a single interface, a new provider is a new class that implements one method and translates its own SDK's exceptions into `AIProviderError`. Nothing else in the application needs to change, and nothing else needs to know which SDK is in use.

**Trade-offs**

Pros

- A new provider can be added without touching `AISummaryService`, the prompt template, or the API route
- Callers handle exactly one exception type regardless of which provider is active
- The service is testable with a fake provider, with no live API call and no SDK-specific mocking required

Cons

- The shared interface is intentionally minimal, a single prompt in and a single string out, so providers with richer capabilities are reduced to that shape for now
- Provider-specific configuration, such as Gemini's timeout, is not yet part of the shared interface and lives on the concrete provider instead

---

# Decision 16: Strict Validation of AI Responses

**Decision**

Parse and validate the AI provider's raw text as a single Pydantic model, `ClinicalSummary`, using `model_validate_json`. Configure both `ClinicalSummary` and its nested `Medication` model with `extra="forbid"`, so a response containing any field outside the documented shape fails validation rather than having the extra field silently dropped. Convert every failure, malformed JSON or a schema mismatch, into the existing `AIProviderError`, so this looks like any other provider failure to the rest of the application.

**Reasoning**

The project's existing rule is that AI responses are untrusted input and must be validated before use. A lenient parse, one that accepts and ignores unexpected fields, would hide the exact situation this rule exists to catch: the model drifting away from the prompt's contract without anyone noticing. Reusing `AIProviderError` rather than introducing a new exception type means the API route did not need to change its error handling to support validation.

**Trade-offs**

Pros

- A response that does not match the documented shape is rejected immediately instead of silently returning incomplete or unexpected data
- One exception type for every provider failure, network, configuration, or validation, so callers only need one `except` clause
- `model_validate_json` reports malformed JSON and schema violations through the same `ValidationError`, so both are handled by one code path

Cons

- A harmless, additive change to the model's output, such as a new field the prompt did not ask for, is rejected the same as a genuinely broken response, rather than being ignored
- The prompt's JSON shape and the Pydantic schema must be kept in sync by hand, since nothing currently generates one from the other

---

# Decision 17: Route Orchestrates Persistence, Service Layer Stays Single-Purpose

**Decision**

`POST /ai/summarize` orchestrates the full flow: create the Analysis, mark it processing, call `AISummaryService` for a validated result, then call a separate persistence function, `persist_analysis_result`, to store it. `AISummaryService` gained no database access to do this. Persistence lives in its own module, `analysis_result_service.py`, which knows about the validated `ClinicalSummary` shape and the database models, but nothing about Gemini or any provider.

**Reasoning**

`AISummaryService` already had one job, turning a provider's raw text into a validated `ClinicalSummary`, and adding database writes to it would have given it two responsibilities that change for different reasons: a new provider or a prompt change affects validation, while a new field to persist or a schema change affects storage. Keeping them apart means a change to one never risks breaking the other, and `AISummaryService` remains testable with a fake provider and no database at all, exactly as it already was.

**Trade-offs**

Pros

- `AISummaryService` still requires no database session to test, even though the feature as a whole now persists data
- Persistence logic can be reused by a future caller that already has a validated `ClinicalSummary` from somewhere other than this route
- The route's control flow directly reflects the two-phase commit pattern (Decision 14): `pending` and `processing` committed on their own, the rest committed or rolled back together

Cons

- The route is less thin than the rest of this project's routes, since it now sequences four separate service calls and handles rollback itself
- A second caller wanting the same orchestration would need to duplicate the route's sequencing and failure handling, since it is not itself extracted into a reusable function

---

# Decision 18: Multi-Stage, Non-Root Dockerfiles with .dockerignore as a Security Fix

**Decision**

Rebuild `backend/Dockerfile` and the newly-added `frontend/Dockerfile` as multi-stage builds (a build stage with the toolchain, a slim runtime stage with only what's needed to run), have the backend's runtime stage run as a dedicated non-root user, and add a `.dockerignore` to both build contexts.

**Reasoning**

Auditing the existing setup for Issue #56 found that `backend/Dockerfile`'s single-stage `COPY . .` had no `.dockerignore` excluding it - a real `docker build` would copy the developer's actual local secrets (`backend/.env`: `DATABASE_URL`, `JWT_SECRET_KEY`, `GEMINI_API_KEY`) directly into an image layer, along with 182 MB of `.venv` and Python/pytest/ruff caches. This is treated as a security fix, not a cleanup nice-to-have: an image is something that gets pushed to a registry and potentially run outside the machine it was built on, and a leaked `.env` baked into a layer stays recoverable from that layer's history even if a later layer overwrites the file. `frontend/Dockerfile` gets the same treatment for the same reason (`frontend/.env`, `node_modules`), and both `.dockerignore` files additionally exclude `tests/`/test-only artifacts and dev caches purely for image size, a secondary concern to the leak itself.

Multi-stage was chosen over the previous single-stage backend Dockerfile because splitting "install dependencies" from "run the application" means the final image never contains pip's build cache or any transient install artifacts - `pip install --prefix=/install` in a `builder` stage, then only `/install` (not the whole stage) is copied into the runtime stage. The backend's runtime stage also drops root: nothing in this application writes to the filesystem at runtime (confirmed by inspection - all persistence goes through the database, not local files), so there is no reason a compromised dependency or a request-handling bug should have root inside the container.

The frontend's runtime stage uses `nginx:alpine` rather than `npm run preview` (Vite's own preview server, explicitly documented as not intended for production) or a Node-based static file server, which would otherwise mean shipping all of Node and `node_modules` in the runtime image just to serve static files a real web server is already built to serve. A small `frontend/nginx.conf` adds one SPA-routing rule (`try_files $uri /index.html`) so a direct load or refresh on a client-side route like `/patients/5` doesn't 404 - without it, nginx has no way to know `/patients/5` isn't a real file and should fall through to the React app.

**Trade-offs**

Pros

- A real, previously-exploitable secret-leak path is closed, not just a size optimization
- The final backend image contains no build tooling, no test suite, and no dev caches - smaller and with a narrower attack surface
- The backend runtime user has no more privilege than the application actually needs
- The frontend's runtime image (nginx + static files) is a fraction of the size of the build stage (Node + `node_modules` + source)

Cons

- Two-stage Dockerfiles are slightly harder to read than the original single-stage version, for a project whose current scale doesn't strictly require multi-stage's size benefits
- `frontend/nginx.conf` is a second thing to keep in sync if the app ever needs more than one SPA-routing rule (a custom 404 page, cache headers, etc.)
- `VITE_API_BASE_URL` must be supplied as a Docker build argument, not a container-runtime environment variable like every other config value in this project - a real deployment has to know to rebuild the image (not just restart the container) to point it at a different backend URL

---

# Decision 19: Automatic Migrations on Backend Startup, Not a Separate Migration Step

**Decision**

`backend/Dockerfile`'s `CMD` runs `alembic upgrade head` before starting `uvicorn`, on every container start - not just the first one, and not as a separate script, job, or manual step a deployer has to remember. `backend/alembic/env.py` was changed to read `DATABASE_URL` from the environment when present, overriding `alembic.ini`'s hardcoded `localhost:5432` default.

**Reasoning**

Deploying to a real EC2 instance for Issue #57 surfaced a gap Issue #56's own build-only validation couldn't have caught: nothing anywhere ran migrations against a genuinely fresh database. Verifying the deployment against a clean Postgres volume hit `relation "users" does not exist` on the first registration attempt - `alembic.ini`'s static `sqlalchemy.url` (correct only when `alembic` runs directly on a developer's host, where the local dev Postgres really is at `localhost:5432`) meant even running `alembic upgrade head` by hand inside the container would have failed to connect at all, since Postgres is a separate container reachable by its Compose service name, not `localhost`.

Running migrations automatically as part of container startup, rather than as a manual step in the deployment runbook, was chosen because a manual step is a manual step someone eventually forgets - and for a single-instance deployment with no concurrent backend replicas, there's no race condition to worry about from running `alembic upgrade head` on every start (a second, third, or hundredth run against an already-current schema is a documented no-op). This is different advice than a multi-replica deployment would need, where multiple containers racing to run migrations simultaneously on startup is a real hazard - but this project is explicitly one EC2 instance, one backend container, by this same issue's own scope.

**Trade-offs**

Pros

- A fresh deployment (or a fresh database volume) works correctly on the very first `docker compose up`, with no separate step to document, remember, or forget
- A schema change ships as part of the same `git pull && docker compose build && docker compose up -d` as any other code change (see `docs/deployment.md`'s Updating the application) - no second command sequence for migrations specifically
- `alembic/env.py`'s `DATABASE_URL` override is backward compatible - a developer running `alembic upgrade head` directly from their host, with no `DATABASE_URL` exported, still gets `alembic.ini`'s original default, unchanged

Cons

- A failed migration now blocks the entire container from starting (it fails before `uvicorn` ever runs), rather than surfacing as a distinguishable error from a running application - correct for a broken schema (the app shouldn't serve traffic against one), but means `docker compose logs backend` is the only way to see what happened, not a live error response
- This approach doesn't extend safely to a multi-replica deployment without additional coordination (a leader-election or a dedicated one-off migration job) - acceptable today given this project's explicit single-instance scope, but a real limitation if that scope ever changes
- No automatic rollback of a migration on deployment rollback (see `docs/deployment.md`'s Rollback procedure) - reversing a specific migration remains a deliberate, manual `alembic downgrade`, never bundled into the generic rollback steps

---

# Decision 20: Structured Failure Detail in AI Provider Logs, Kept Server-Side Only

**Decision**

`GeminiProvider._log_failure` now logs a `detail` field alongside the existing `error_type` - the Gemini API's own `message`/`status` for an `APIError` (e.g. `"models/gemini-2.0-flash is not found"`, `"RESOURCE_EXHAUSTED"`), or `str(error)` for any other exception. This is added only to the `logger.warning(...)` call; the `AIProviderError` message raised to the caller (and, from there, returned to the frontend as the `503` response's `detail`) is unchanged.

**Reasoning**

Google retired `gemini-2.0-flash` (the application's configured model at the time) server-side, breaking every AI-dependent request in production. Diagnosing it took longer than it should have, because the only thing the failure log ever recorded was `error_type=ClientError` - true, but equally true of a network blip, an invalid API key, or a malformed request. The Gemini SDK's own `APIError` already carries a specific, human-readable description of what actually went wrong (`.message`/`.status`); it was simply never read.

Keeping `detail` out of the user-facing `AIProviderError` message is deliberate, not an oversight: `_safe_error_message` (`app/api/routes/analyses.py`) already passes an `AIProviderError`'s `str()` straight through to the API response's `detail` field (see `docs/api.md`'s `503` documentation), so anything added to that exception's message reaches the frontend, and from there, whoever is looking at the browser's network tab. A raw Gemini API error string is exactly the kind of "provider internals" that shouldn't be exposed - not because a model name is secret, but because a third-party API's internal error vocabulary is not a contract this application should commit to exposing to its own users. The fix is additive purely to the log line, which only server operators can read.

**Trade-offs**

Pros

- A future provider-side failure (a retired model, a quota change, an invalid request shape) is diagnosable directly from `docker compose logs backend`, without reproducing the request by hand or reading Google's own status page first
- The user-facing `503` response is provably unchanged - covered by a test asserting the logged `detail` and the raised exception's message never contain the same string (`tests/test_gemini_provider.py`)
- No new dependency, no new log destination - the existing `logging` module and existing log line, extended with one more field

Cons

- `detail` is one more thing to trust `APIError.message` to never contain - a hard boundary to prove permanently at the library level, only reasoned about here (Google's SDK sends the API key via header, never in a URL or an exception message, and a validation/safety-block error surfaces through an empty response, not this exception path - see `docs/ai.md`'s Logging section) rather than mechanically enforced
- `str(error)` for a non-`APIError` exception is unstructured and could, for some unanticipated exception type, be more verbose than intended - accepted as a reasonable trade-off for visibility into failure modes this code can't fully enumerate in advance

---

# Decision 21: Pluggable StorageService Interface for File Storage, Mirroring the AI Provider Pattern

**Decision**

Introduce `StorageService`, an abstract interface (`upload`/`download`/`delete`) with two implementations - `LocalStorageService` (the default, writes to a local directory) and `S3StorageService` (uploads to a private S3 bucket via `boto3`) - selected by one setting, `Settings.storage_backend`, through a single factory function (`build_storage_service`). Every other part of the application (the clinical document routes and service) depends only on the `StorageService` interface, injected via FastAPI's dependency system, never on a concrete backend class.

**Reasoning**

This application already had exactly this problem once, for AI providers (Decision 15): business logic needing an external capability whose concrete implementation should be swappable without touching that logic. `AIProvider` solved it with a minimal interface, a factory function, and dependency injection - `StorageService` reuses the identical shape rather than inventing a new pattern for a structurally identical problem. The alternative - `if settings.storage_backend == "s3": ... else: ...` conditionals wherever a file is read or written - would scatter the same branch across every call site and make adding a third backend (or testing against a fake one) require finding and updating every one of them individually.

Before this feature, no file storage of any kind existed in the application - uploaded files were read into memory, text-extracted, and discarded (see `docs/data-model.md`'s Design Decisions). This is worth being explicit about because the interface was designed for the problem this application actually has (an original file plus its already-separately-stored extracted text) rather than adapted from a different one; `StorageService` has no method for anything analysis-related, since AI analysis was never going to read through it - it continues reading `raw_text` from Postgres exactly as before.

**Trade-offs**

Pros

- A new backend (e.g. a different cloud provider, or Google Cloud Storage) is a new class implementing three methods, not a change to any route or service
- `LocalStorageService` makes local development, CI, and this feature's own test suite fully independent of AWS - no account, no credentials, no network call, ever, unless a test explicitly opts into `S3StorageService` (via `moto`, which mocks the AWS API rather than calling it for real)
- Settings validates S3 configuration at startup (a `model_validator`, not a lazy check on first upload) - a misconfigured `STORAGE_BACKEND=s3` fails immediately and clearly, the same "fail fast, not on first use" principle Decision 19 already established for a different startup-time failure mode

Cons

- Two implementations to keep behaviorally consistent (e.g. both raise `ObjectNotFoundError`, not just a generic exception, for a missing key) - enforced only by a shared test suite (`tests/test_storage_service.py` runs the same assertions against both), not by the type system
- `LocalStorageService`'s sidecar `.meta.json` file (recording content type, which a plain filesystem has no native concept of) is a small, backend-specific implementation detail that `S3StorageService` doesn't need at all, since S3 stores content type as real object metadata - an asymmetry between the two implementations that the shared interface itself doesn't surface

---

# Decision 22: Centrally-Configured Structured Logging with an Allowlist for Log Fields

**Decision**

One module, `app/core/logging_config.py`, owns all logging configuration for the entire backend - handler, formatter, and a `logging.Filter` that injects request-scoped context - configured once at import time (`configure_logging`, called from `app/main.py`) on the root logger, so every existing `logging.getLogger(__name__)` call in the codebase is picked up without being changed itself. Every log record is rendered through a fixed allowlist of field names (`ALLOWED_FIELDS`): a field passed via `extra={...}` that isn't in this tuple is silently dropped by both formatters, rather than reaching a log line.

**Reasoning**

The alternative to centralizing configuration - each module calling `logging.basicConfig` or configuring its own handler - was already implicitly ruled out by there being no logging configuration at all before this issue (four loggers running on Python's default, unconfigured root logger). A single `configure_x(app, ...)` function wired up once from `app/main.py` is the pattern this codebase already uses for other cross-cutting concerns (`configure_cors`); logging fits the same shape rather than inventing a new one.

The allowlist is the more consequential decision. This application handles synthetic clinical data, but the logging code that handles it doesn't get to assume every future call site will remember that credentials, tokens, prompts, and document text must never be logged - a project convention enforced only by developer discipline doesn't survive a rushed debugging session where someone adds `extra={"raw_response": response}` to see what a failure looked like. Making the field list an allowlist, not a denylist, means that mistake fails safe: the added field simply never appears in the rendered output until someone deliberately adds it to `ALLOWED_FIELDS`, a small, visible, single-file change that's easy to catch in review. A denylist (block known-bad field names) would have the opposite failure mode - safe only until someone invents a new sensitive field name the denylist doesn't yet know about.

`user_id` specifically could not be carried the same way as `request_id`/`method`/`path`/`client_ip` (all via a `contextvars.ContextVar`, set once by the request-logging middleware and read by every log call during that request). Every dependency and route handler in this codebase is a synchronous `def`, and Starlette runs each one via `run_in_threadpool`, which executes it inside its own *copy* of the current context - a `ContextVar.set()` made inside `get_current_user` (itself a sync dependency) is invisible to sibling dependencies or to the middleware's own code, even within the same request, even on the same thread (verified empirically: a minimal diagnostic FastAPI app with three sync dependencies sharing one OS thread still couldn't see one dependency's `ContextVar.set()` from another). `request.state` - a plain mutable attribute on the one `Request` object every dependency and the middleware share - is not subject to that per-call context-copy isolation, so `user_id` rides `request.state` instead, read back by the middleware after `call_next()` returns.

**Trade-offs**

Pros

- A field can never leak into a log line by accident - it must be added to `ALLOWED_FIELDS` first, a deliberate, reviewable step, not a runtime configuration flag someone could get wrong
- Zero new third-party dependencies - the standard library's `logging` module, already in use, is centrally configured rather than replaced
- JSON in production (`JSONFormatter`), a readable single line in development (`ConsoleFormatter`) - the same underlying fields either way, so a log aggregator and a developer's terminal never disagree about what's available, only how it's displayed

Cons

- The allowlist is one more place to update when a genuinely new, safe field is needed - a small but real tax on adding new structured log data going forward
- `user_id`'s `request.state`-based path is asymmetric with every other context field (which use the `ContextVar` uniformly) - a direct consequence of this codebase's synchronous-dependency architecture rather than a free design choice, and worth knowing about before assuming a new context field can simply be added to `RequestContextFilter._CONTEXT_FIELDS` without checking whether it's set from inside a sync dependency the same way `user_id` is

---

# Decision 23: BuildKit Cache Mounts Instead of `--no-cache-dir`, Paired with GitHub Actions Cache in CI

**Decision**

`backend/Dockerfile`'s `pip install` and `frontend/Dockerfile`'s `npm ci` each run under a BuildKit cache mount (`--mount=type=cache,target=...`) rather than downloading fresh on every build. `backend/Dockerfile` drops `--no-cache-dir` (Decision 18's original flag) since the cache mount now serves the same purpose more effectively. Both Dockerfiles gain a `# syntax=docker/dockerfile:1` pragma, required for the mount syntax to resolve consistently. In CI, both `backend.yml` and `frontend.yml`'s "Validate Docker image build" step moves from a plain `docker build` to `docker/build-push-action` with `cache-from`/`cache-to: type=gha`.

**Reasoning**

Decision 18 chose `--no-cache-dir` deliberately, to keep pip's download cache out of the final image layer. That reasoning is still correct about the image, but it also means every single build - local or CI - re-downloads every dependency from PyPI, even when `requirements.txt` changed by one line. A BuildKit cache mount gets the same "nothing extra in the final image" property (a mount is never part of an exported layer, unlike a normal on-disk directory would be) while *also* persisting the downloaded packages between builds, in BuildKit's own cache store - strictly better than `--no-cache-dir` for this project's actual goal (a small image), not a trade-off against it.

That local persistence alone doesn't help CI, though: each GitHub Actions job starts on a fresh runner with no prior BuildKit state at all, so a cache mount with nothing to restore from behaves exactly like `--no-cache-dir` did. `cache-from`/`cache-to: type=gha` closes that gap - it's what actually gives the mount something to be warm *from* on the next run, by storing and restoring the same BuildKit cache (both ordinary layers and cache-mount contents) through GitHub's own Actions cache rather than requiring the runner itself to persist anything.

Neither change touches the Dockerfiles' runtime behavior at all: it's the same `pip install --prefix=/install`/`npm ci` producing the identical installed package set, only how the download step is cached. `docker/build-push-action` is used with `load: true`, never `push: true` - CI still only proves the image builds, exactly as the plain `docker build` it replaces did; nothing is published anywhere new.
# Decision 23: Same-Origin Deployment via nginx Reverse Proxy, Backend Made Internal-Only

**Decision**

The frontend's nginx container now reverse-proxies `/api/*` to the backend over the Docker network (`frontend/nginx.conf`), and the backend's host port is bound to `127.0.0.1` only (`infra/docker-compose.yml`), the same treatment `postgres` already had. The browser now reaches the entire application - SPA and API alike - through one origin; it never talks to the backend's own port at all. `VITE_API_BASE_URL` (baked into the frontend bundle at image build time) changes from an absolute URL to a relative path, `/api`, so the frontend never needs to know the backend's hostname, port, or protocol. `CORS_ALLOWED_ORIGINS` - the setting that let a deployed frontend's origin call the backend cross-origin - is removed entirely; nothing needs it anymore.

**Reasoning**

Before this, the backend's port had to be published publicly (`0.0.0.0`, reachable from the internet) purely so the browser could reach it directly, and the frontend had to be told that URL at image build time - which is also why a real deployment (`docs/deployment.md`'s AWS EC2 section) needed the instance's public IP known *before* building the frontend image, and why CORS existed as a whole layer of configuration in the first place. A reverse proxy removes the reason for all three: the backend is reachable by a fixed Docker Compose service name from inside the same container network nginx already runs in, so there's no reason for anything outside that network to reach it directly, and no cross-origin request for the browser to ever make.

The CORS middleware itself is *not* removed, despite that - `npm run dev` (Vite's dev server, `docs/deployment.md`'s Local Development section) runs directly on a developer's host with no reverse proxy in front of it at all, and still makes a real cross-origin request to the backend's own port. That's the one genuine cross-origin case left in this application, and it still needs CORS to work; `configure_cors` (`app/main.py`) is scoped down to exactly that case (the existing `LOCALHOST_ORIGIN_REGEX`, unchanged, restricted to `app_env == "development"`) rather than removed outright.

Two problems specific to reverse-proxying a service by its Compose name, not obvious from the requirement alone, had to be solved directly in `frontend/nginx.conf`:

- **Stale upstream DNS after a partial redeploy.** `docs/deployment.md`'s own documented update flow rebuilds and recreates only the container whose image changed - a backend-only change never touches the running frontend container. A plain `proxy_pass http://backend:8000` resolves `backend`'s address once, at nginx startup, and caches it for the life of the worker process; after backend is recreated (a new container, typically a new IP), nginx would keep proxying to the dead address until it was *also* restarted - an outage this application's own deployment workflow would trigger on every backend-only update. Fixed with `resolver 127.0.0.11` (Docker's embedded DNS, present on every Compose network) plus a variable in `proxy_pass`, which defers resolution to request time instead of caching it from startup.
- **The same fix also removes the need for `frontend: depends_on: backend`.** A static `proxy_pass` would need `backend`'s DNS name to exist by the time nginx starts, or nginx fails to start entirely (a fatal "host not found in upstream" error) - which would have meant re-adding the `depends_on: backend` that Issue #183 had specifically removed as unnecessary. The dynamic resolver above doesn't have this problem: nginx starts successfully even if `backend` doesn't exist yet, serves `/api/*` as `502` until it does, and self-heals with no restart needed once it appears - verified directly (`docker compose rm -f backend`, restart `frontend`, confirm it stays healthy and serves the SPA; bring `backend` back, confirm `/api/health` starts working with no action on `frontend`). This preserves Issue #183's "no unnecessary waiting" startup ordering rather than reintroducing the dependency this issue's own architecture change might otherwise have required.

A third, easy-to-miss correctness issue: without explicit forwarding, every request the backend sees would show nginx's own Docker-network address as its `client_ip` (Issue #59's structured logging), not the real visitor's - `proxy_set_header X-Real-IP`/`X-Forwarded-For`/`X-Forwarded-Proto` in nginx, paired with `--forwarded-allow-ips='*'` on the backend's `uvicorn` invocation (`backend/Dockerfile`), fixes this. Trusting every source for that flag is safe specifically *because* of this same decision - the backend's port is no longer reachable by anything except nginx (and the host itself, for direct local access), so there's no untrusted party in a position to spoof those headers in the first place.

**Trade-offs**

Pros

- Both a `requirements.txt`/`package-lock.json` change (verified locally: every package installed from `Using cached ...` wheels, zero PyPI network requests) and, once the GHA cache is warm, every CI run after the first benefit - not just an incremental improvement to the already-fast "source-only change" case Decision 18's layer ordering already handled well
- No change to the final image's contents or size - a cache mount was chosen specifically because it doesn't reintroduce what `--no-cache-dir` was removing
- Uses GitHub's own Actions cache - no new CI system, no external cache service, no additional secrets or registry login

Cons

- Requires a BuildKit-aware builder (the default in any current Docker Engine/Compose, and on `docker/setup-buildx-action`-equipped GitHub runners, but a genuinely old or non-BuildKit `docker build` would no longer understand the mount syntax at all - mitigated by the `# syntax=` pragma, not eliminated)
- The GHA cache has its own eviction/size limits and is scoped per-repository, so a cache miss (a new branch, an evicted entry) still falls back to a full rebuild - an improvement to the common case, not a guarantee every build is fast
- One more moving part in the CI workflow files (`docker/setup-buildx-action`, `docker/build-push-action`) in place of a single `docker build` line - more to understand when reading the workflow, in exchange for the caching behavior neither could express alone
- One fewer thing to expose to the internet in production - the backend's own port is never reachable from outside the host at all, closing an attack surface that existed purely so the browser could reach it directly
- The frontend image no longer needs the deployment's public hostname baked in at build time - `VITE_API_BASE_URL=/api` works unmodified for local Docker Compose *and* a real deployment, simplifying "Step 5: Configure environment variables" in `docs/deployment.md`'s AWS EC2 runbook to one fewer value to get right before building
- Zero CORS preflight requests during normal application use (verified: no `Access-Control-*` response headers on any same-origin request through nginx) - one fewer request per API call in practice, and one fewer category of "why did this fail in production but work locally" bug class removed with it

Cons

- One more moving part in `frontend/nginx.conf` - a resolver, a rewrite, and forwarded headers, none of which are needed for `nginx.conf`'s previous job (serving static files) - all directly required to reverse-proxy correctly, not incidental complexity, but genuinely more nginx configuration to reason about than before
- `npm run dev`'s dev-server flow and the Docker Compose/production flow now differ in an important way (one is cross-origin and needs CORS + an absolute backend URL, the other is same-origin and needs neither) - worth knowing about before assuming they behave identically, though each is now documented at its own env var (`frontend/.env.example`, `infra/.env.example`)

---

# Future Decisions

Additional architectural decisions will be documented as the project evolves, including topics such as:

- Background job processing
- Caching
- AWS architecture
- Deployment strategy
- Monitoring
- Performance optimization