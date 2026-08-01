# Testing

## Overview

MedLens backend tests are written with `pytest` and exercise the API the same way a real client would, using FastAPI's `TestClient`. Rather than mocking the database, tests run against a real, isolated PostgreSQL database so that ORM behavior, password hashing, and JWT creation and verification are all exercised as they would be in production.

Tests are part of the definition of done for backend features.

---

## Test Stack

- pytest
- FastAPI TestClient
- PostgreSQL

---

## Running Tests

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -v
```

The local PostgreSQL container must be running (`docker compose up --build` from `infra/`), since tests connect to it over `localhost:5432`.

`pytest.ini`'s `pythonpath = .` (Issue #54) is what makes `from app... import ...` resolvable inside `tests/conftest.py` for the plain `pytest` command above. Without it, `app` is only importable when pytest happens to be invoked as `python -m pytest` instead - `python -m` prepends the current directory to `sys.path` as a side effect of `-m` itself, which masks the gap during local ad hoc use but doesn't help GitHub Actions or any other caller of the plain `pytest` command this file documents. Discovered when `.github/workflows/backend.yml` ran `pytest -v` for the first time and failed with `ModuleNotFoundError: No module named 'app'` before this line existed.

---

## Linting and Formatting (Issue #52)

The backend has no `Makefile`/`uv`/`poetry` task runner - just `pip` and `requirements*.txt` - so the commands below are the recommended way to run the quality pipeline directly, the same way `pytest -v` already is above.

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt   # installs ruff alongside pytest/httpx/reportlab

ruff check .                          # lint
ruff check . --fix                    # lint, auto-fixing what's safely fixable
ruff format .                         # format
ruff format --check .                 # format, but only report - CI will use this form
```

These are the exact commands CI runs (see "Continuous Integration" below) - passing all four locally is the same bar CI holds a branch to.

**Tool choice**: a single tool, Ruff, covers linting, import sorting, and formatting - there was no previous Black/isort/flake8 setup to reconcile or migrate off of; this is the project's first backend lint/format configuration. Using one tool instead of three avoids the class of bugs where a formatter and a linter disagree about the "correct" style and fight each other on every commit.

**Configuration** lives in `backend/pyproject.toml` (the project has no other use for that file yet - no `[build-system]`/`[project]` table, just `[tool.ruff]`). Enabled rule sets: pycodestyle (`E`/`W`), Pyflakes (`F`), isort (`I`), pyupgrade (`UP`), flake8-bugbear (`B`), flake8-comprehensions (`C4`), flake8-simplify (`SIM`), and Ruff's own additional rules (`RUF`). Line length is 100, matching the frontend's Prettier `printWidth` (`frontend/.prettierrc.json`) so both halves of the project agree on one convention.

**Intentionally ignored rules** (each documented again, in more detail, directly above its entry in `pyproject.toml`):

- **`E501`** (line too long) - the formatter already wraps every line of code it can; what's left is either a long string that can't be safely rewrapped without changing its meaning (the natural-language AI prompt text in `app/ai/prompts.py`) or a long URL in a comment. Ruff's own docs recommend disabling `E501` for exactly this reason when its formatter is in use.
- **`UP042`** (`class Foo(str, Enum)` → `class Foo(StrEnum)`) - every API schema enum (`AnalysisStatus`, `DiscrepancyType`, `DiscrepancySeverity`, `ResolutionStatus`) uses the `str, Enum` mixin today. `enum.StrEnum` isn't a guaranteed drop-in replacement - it changes how members format via `str()`/f-strings, which could silently alter API response bodies or log output. Issue #52 is lint/format only ("do not change application behavior"), so this stays off; it's a candidate for its own deliberate, tested issue later, not a side effect of this one.

**`B008`** (function call in default argument) is *not* ignored, but is narrowed: FastAPI's dependency injection is `Depends(...)`/`Query(...)`/`File(...)`/`Form(...)` used as a parameter default - that's the framework's documented API, not the mutable-default-argument bug `B008` exists to catch. `[tool.ruff.lint.flake8-bugbear] extend-immutable-calls` allowlists exactly those FastAPI callables, so `B008` stays active for everything else (a plain `def f(x=some_call())` elsewhere in the codebase would still be flagged).

No `noqa` comments were added or needed beyond the one already in `alembic/env.py` (`import app.models  # noqa: F401`, a deliberate side-effect import that registers every model on `Base.metadata` before Alembic reads it - see the comment above it).

---

## Continuous Integration (Issue #54)

`.github/workflows/backend.yml` runs on every push and pull request to `main` or `develop` that touches `backend/**` (or the workflow file itself) - a frontend-only or docs-only change doesn't trigger it. It's a single `ubuntu-latest` job that checks out the repo, starts a `postgres:16` service container (same image and credentials as `infra/docker-compose.yml`'s local dev Postgres, reachable at `localhost:5432` exactly like `docs/testing.md`'s "Running Tests" section already describes), sets up Python 3.12 with `actions/setup-python`'s built-in pip cache (keyed off `backend/requirements.txt` and `backend/requirements-dev.txt`), runs `pip install -r requirements-dev.txt`, and then runs `ruff format --check .`, `ruff check .`, and `pytest -v` in that order - the same commands documented above, never invoked differently. Any one of those three failing fails the whole workflow (a step failure stops the job by default - no special configuration needed for that). There's no matrix or parallel job - a single Python version and a single job is enough for an application, not a published library supporting a range of runtimes.

`DATABASE_URL` and `JWT_SECRET_KEY` are set directly in the workflow's `env:` block, since `app/core/config.py`'s `Settings()` reads them eagerly at import time and there's no `.env` file in CI (it's gitignored). Neither is a real secret in this context - the Postgres database and the whole VM are discarded when the job ends, and `JWT_SECRET_KEY` only needs to be *some* string for token signing to work inside that one run.

**`GEMINI_API_KEY` is deliberately never set.** `test_summarize_uses_real_gemini_provider_by_default_when_key_missing` (`tests/test_analyses.py`) asserts a 503 when the key is missing - the one environmental flake mentioned throughout this project's history, which only ever failed on a local machine that happened to already have a real key exported in its shell. GitHub Actions never injects a secret into a job unless a workflow step explicitly references it via `secrets.<name>`; this workflow does not reference `secrets.GEMINI_API_KEY` (or any secret) anywhere, so the variable is simply absent in the job's environment - exactly the condition the test expects - with no extra handling, workaround, or weakening of the test required. (Secrets are also never exposed to `pull_request` runs from forked repositories at all, which would be a second, independent reason this stays safe if the project ever accepted outside contributions - but the first reason alone is sufficient here.)

A red check on a PR always reproduces locally with the exact command named in that step's log - `ruff format --check .`, `ruff check .`, or `pytest -v` - run from `backend/` with the local Postgres running (`docker compose up --build` from `infra/`, per "Running Tests" above).

**`docker build` is the workflow's final step (Issue #56).** After `pytest -v` passes, the job runs `docker build -t medlens-backend:ci .` from `backend/` - proving the production image (`backend/Dockerfile`) still builds on every push and PR, not just whenever someone happens to build it by hand before a deploy. This is deliberately the last step of the *same* `quality` job, not a second job or a second workflow file - Issue #56 asked for Docker validation to extend the existing pipeline, not duplicate it. The build needs no environment variables and never runs the resulting image (`Settings()`'s required `DATABASE_URL`/`JWT_SECRET_KEY` are only read when a container actually starts, which `docker build` doesn't do) - it only proves the image is buildable, the same narrow scope the local verification in `docs/deployment.md`'s Docker Image Builds section uses. See that section for the Dockerfile itself (multi-stage, non-root, `.dockerignore`) and `docs/design-decisions.md` (Decision 18) for why.

---

## Test Database

Tests never run against `medlens_db`, the development database.

Before the application is imported, the test suite rewrites the `DATABASE_URL` environment variable to point at a separate database, `medlens_test_db`, on the same local PostgreSQL server. Because the backend's settings and database engine are constructed from environment variables at import time, this makes the entire application — including code paths that talk to the database directly — use the isolated test database automatically, with no need for dependency overrides or mocks.

`medlens_test_db` is created automatically on first run if it does not already exist, and its schema is created from the SQLAlchemy models.

### Isolation Between Tests

After each test, all rows are removed from every table so that each test starts from a clean slate without needing to recreate the schema. Tests that need a user (for example, to log in or call `/users/me`) create one through the real `/auth/register` and `/auth/login` endpoints as part of the test itself.

---

## Current Coverage

- **Health endpoint** — `GET /health` returns a successful status with a connected database.
- **Registration** — successful registration, rejection of duplicate emails, rejection of invalid email formats, rejection of passwords shorter than 8 characters, and correct handling of an optional name.
- **Login** — successful login returns a bearer token whose decoded claims match the authenticated user; incorrect passwords and unknown emails are both rejected.
- **JWT authentication** — the `get_current_user` dependency is exercised end-to-end through `/users/me`, covering missing, malformed, expired, and otherwise invalid tokens, as well as a validly signed token referencing a user that no longer exists.
- **/users/me** — returns the authenticated user's profile and never exposes the stored password hash.
- **Medications**: full CRUD (create, list, retrieve, partial update, delete) scoped to the authenticated user, plus CSV import covering successful multi-row imports, optional field handling, file type and encoding validation, header validation, blank row handling, whitespace trimming, per-row field validation, atomic rejection when any row is invalid, and ownership isolation.
- **Medication reconciliation findings**: model creation, each allowed finding type, severity, and resolution status value, rejection of invalid values, nullable medication and medication mention references, relationships to Analysis, Medication, and MedicationMention, response schema serialization, a database constraint on the required analysis reference, and deletion behavior, including cascade deletion from Analysis and reference clearing when a Medication or MedicationMention is deleted.
- **Analysis**: model creation with a default pending status, every allowed status value and rejection of an invalid one, nonnegative validation on summary counts, the user relationship, attaching multiple clinical documents to one analysis and one document to multiple analyses, the discrepancy relationship, cascade deletion of discrepancies when an analysis is deleted, association cleanup when a clinical document is deleted, response schema serialization, the processing, completed, and failed transitions, timestamp behavior across the lifecycle, error message handling, and provider and model metadata.
- **Medication normalization**: trimming, lowercasing, and whitespace collapsing for medication names and comparable fields, the trailing period rule for names, the known route and frequency aliases, and confirmation that unrelated or partially matching names are never treated as equivalent.
- **Medication reconciliation service**: each supported discrepancy rule in isolation, including the discontinued-status case taking precedence over the general status conflict, no finding when only one side has a comparable value (covering both the medication and the mention lacking the value), no finding for values that are equivalent after normalization including case-insensitive name matching, exact matches on every field producing no discrepancies at all, matching and mismatching status values including an unrecognized status string falling back to the general status conflict rather than the discontinued-specific one, deduplication of identical mentions into a single finding, separate findings for genuinely distinct conflicting values, multiple distinct discrepancy types coexisting correctly in a single reconciliation run, correct linkage to the originating Medication and MedicationMention, the centralized severity mapping, full orchestration through `run_medication_reconciliation` including status and timestamp progression, count totals, provider and model metadata, rejection of a nonexistent or another user's document, a selected document with no mentions completing successfully, rollback of staged discrepancies and a sanitized error message on an unexpected failure, and isolation from another user's medications.
- **AI prompt building**: every supplied note appears in the generated prompt, notes are numbered in order, the instructions to identify medications and to avoid attempting reconciliation are present, and an empty note list is rejected.
- **AI summary service**: `AISummaryService` is tested against a fake in-memory provider rather than a live call, covering provider and model metadata on the result, a valid response parsed into a `ClinicalSummary` with all fields populated, optional medication fields correctly defaulting to null when omitted, empty medication and inconsistency lists, the prompt reaching the provider, propagation of a provider error, and rejection of an empty note list. Response validation is covered separately: malformed JSON, a missing required field at the top level and within a medication entry, an incorrect field type at both levels, an unexpected extra field at both levels, and an unexpected top-level JSON structure (a list instead of an object) are all rejected as `AIProviderError`.
- **Gemini provider**: the underlying `google.genai.Client` is mocked rather than called live, covering a missing API key failing before any client is constructed, a successful call returning the response text, that the request is made with Gemini's JSON response mime type set, translation of both an SDK API error and an unexpected exception into `AIProviderError`, rejection of an empty or missing response, and that the client is constructed once and reused across calls.
- **Analysis result persistence**: `persist_analysis_result` is tested directly against the isolated test database, covering a successful result with its Analysis fields, medication mention, and inconsistency all persisted correctly, multiple medications, multiple inconsistencies, an empty medication list, an empty inconsistency list, and rollback when the underlying completion step fails, confirming no medication mention or inconsistency rows survive and the Analysis remains in its prior state.
- **AI summarize endpoint**: authentication is required, a successful request returns `201` with the created `analysis_id` plus the parsed medications, inconsistencies, and summary for the caller's own documents using an overridden fake provider, and the corresponding Analysis, medication mention, and inconsistency rows are confirmed persisted directly against the database. Multiple documents are combined into one prompt. A nonexistent or another user's document is rejected the same way as elsewhere in the API, with no Analysis created. An empty document id list is rejected. A provider failure and a provider response that fails schema validation both surface as a `503` and leave the Analysis persisted as `failed` with the same sanitized message returned in the response. The real, non-mocked provider wiring fails gracefully with a `503` when no API key is configured in the test environment, and that failure is persisted as well.
- **Analysis detail retrieval**: `get_analysis_for_user` is tested directly against the isolated test database, covering a caller retrieving their own analysis with its mentions and inconsistencies loaded, `None` returned for another user's analysis and for a nonexistent id. Ordering is not asserted at this layer, since sorting happens when the response is built, not in this function. The `GET /ai/analyses/{analysis_id}` endpoint is tested end to end, covering authentication being required, a persisted completed analysis returned with its mentions, inconsistencies, and a `null` `error_message`, an analysis with no medications, an analysis with no inconsistencies, deterministic ascending-id ordering of both lists, a failed analysis returning the same sanitized `error_message` persisted by `POST /ai/summarize` with empty mention and inconsistency lists, rejection of another user's analysis, and rejection of a nonexistent analysis, all with a `404` and the same message so existence is never leaked.
- **Complete analysis workflow (integration)**: a single end-to-end test chains registration, login, clinical document creation, `POST /ai/summarize` with a mocked AI provider, and `GET /ai/analyses/{analysis_id}` together in one run, then cross-checks that both endpoints describe the same persisted analysis. Unlike the per-component tests above, this test exists to catch integration failures between components that are individually well covered but not otherwise exercised together in one continuous request flow, including ownership enforcement carried through to the end of that flow.
- **Analysis deletion**: `delete_analysis` is tested directly against the isolated test database, covering successful deletion of an owned analysis, cascade deletion of its `AnalysisMedicationMention` and `AnalysisInconsistency` rows, `False` returned for another user's analysis and for a nonexistent id with the analysis left untouched, and clinical documents, medications, and users all remaining intact. The `DELETE /ai/analyses/{analysis_id}` endpoint is tested end to end, covering authentication being required, a successful `204` with an empty body that also removes the persisted mentions and inconsistencies and makes the analysis unretrievable through `GET /ai/analyses/{analysis_id}` afterward, the linked clinical document remaining retrievable after the analysis is deleted, and rejection of another user's analysis and of a nonexistent analysis with the same `404` used elsewhere.
- **Analysis listing**: `list_analyses_for_user` is tested directly against the isolated test database, covering an empty list for a user with no analyses, only the caller's own analyses ever being returned, descending-id ordering (most recent first), the `limit` parameter capping the number of rows returned, and the `clinical_documents` relationship loading correctly for computing a document count. The `GET /ai/analyses` endpoint is tested end to end, covering authentication being required, an empty list for a new user, every field on a returned row including `document_count` and the absence of full mention/inconsistency detail, isolation from another user's analyses, descending-id ordering, the `limit` query parameter, and rejection of a `limit` outside the documented `1`-`50` range with a `422`.
- **Configuration** — application settings load expected values from environment variables and fall back to documented defaults when optional values are not set.

---

## Future Testing

- Frontend (Vitest and React Testing Library)
- CI/CD (running the backend test suite automatically on pull requests via GitHub Actions)
