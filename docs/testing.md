# Testing

## Overview

MedLens has two independent test suites, one per half of the application: a `pytest` suite for the FastAPI backend (537 tests across 24 files) and a Vitest suite for the React frontend (around 600 tests across 64 files). Both run against the real behavior of the code they're testing rather than a simplified stand-in of it wherever practical: the backend suite exercises a real, isolated PostgreSQL database through FastAPI's own `TestClient`, and the frontend suite renders real components through React Testing Library rather than asserting against a shallow render tree.

Tests are part of the definition of done for a feature in this project, not a separate pass added afterward. Every issue implemented in this codebase's history has included the tests for what it added, in the same change.

This document describes what actually exists today. Where a testing capability doesn't exist yet, and a few genuinely don't, listed plainly in Coverage below, this document says so rather than describing it as if it were already there.

---

## Testing Philosophy

### Why this project emphasizes testing

MedLens is a portfolio project, but it's built to the standard of production software, not a demo that only has to work once for a screen recording. A synthetic-data clinical reconciliation tool has a specific reason to take correctness seriously even though no real patient data is ever at stake (Decision 8, `docs/design-decisions.md`): the whole point of the application is producing a trustworthy answer to "does this patient's medication list match what their clinical notes actually say": a wrong answer here is the kind of bug that matters in the domain being simulated, even in a synthetic form. Tests are also this project's primary evidence that a change didn't silently break something else; with no dedicated QA and no manual regression pass before every deploy, the test suite is what actually stands in for both.

### The testing pyramid, as actually reflected here

The backend suite is weighted toward the middle of the pyramid rather than a strict "mostly unit tests" shape. Most backend test files exercise a real Postgres database directly, either through a full HTTP request via `TestClient` (route-level tests) or by calling a service/model function directly against the same real database (service- and model-level tests), because the ORM behavior, constraints, and cascade rules those layers depend on are exactly the kind of thing a mocked database would let pass incorrectly. True unit tests (no database, no HTTP) exist too, for logic that's genuinely pure, medication name normalization, AI prompt construction, JWT/CORS/logging-formatter behavior, and are used specifically where the thing under test doesn't touch the database or the network at all. One deliberate end-to-end integration test (`test_analysis_workflow_integration.py`) chains registration through analysis creation through analysis retrieval in a single test, specifically to catch a failure mode none of the narrower tests around it can: two components that are each correct in isolation but disagree about the contract between them.

The frontend suite is the more conventional shape: predominantly small, isolated unit/component tests (a hook tested with `renderHook`, a component tested with `render`, a pure validation function tested directly), each with the layer below it mocked (a hook test mocks the `@/api/*` module it calls; a page test mocks the hooks it calls), plus a smaller number of page- and route-level tests that render a fuller tree (a whole page, or the app's route table) to catch wiring mistakes between components that unit tests can't see. There is no end-to-end browser suite (no Playwright/Cypress) on either side; see "What is not tested" below.

### What is tested

- Every backend API route: success paths, validation failures, authentication/authorization enforcement, and ownership isolation (one user's data is never visible to another).
- Backend business logic in isolation from HTTP: medication normalization, medication reconciliation, AI response validation, analysis persistence.
- Database-level behavior that only a real database can prove: foreign key constraints, `ON DELETE` cascade/set-null behavior (Decision 10, Decision 11), uniqueness constraints.
- Integration points with external services, via a deliberate mock at the SDK/HTTP boundary: the Gemini SDK client, OpenBioLLM's/MedGemma's local Ollama HTTP calls (`urllib.request.urlopen`), S3 (via `moto`), never a live network call, and never a running Ollama server, in the test suite.
- Structured logging: that specific fields appear on specific log events, and, just as important, that sensitive fields (passwords, tokens, prompts, document content) never do.
- Frontend hooks, components, pages, and the route table, each rendered for real and asserted against with React Testing Library's user-facing queries (`getByRole`, `getByLabelText`) rather than implementation details.
- Frontend form validation logic, in isolation from any component that uses it.

### What is not tested (and why)

- **No end-to-end browser tests** (Playwright, Cypress, Selenium). Every user-facing flow that would require one is instead covered by a combination of backend route tests (proving the API contract) and frontend page/hook tests with the API mocked (proving the UI calls it correctly and renders the result); a real gap in true end-to-end confidence, accepted as a scope decision for a single-developer project rather than a discovered oversight.
- **No automated migration tests.** See "Migration testing" under Backend Testing below for what does and doesn't verify a migration.
- **No dedicated accessibility audit tool** (no `jest-axe`/`@axe-core`). See "Accessibility in tests" under Frontend Testing below for what does provide partial coverage here.
- **No load or performance testing.** Timing metrics (`duration_ms` on structured log events) give visibility into how long things take in a real deployment, but nothing in the test suite asserts a performance budget or simulates concurrent load.
- **No automated Docker Compose / deployment verification.** `docker build` for both images is validated in CI (see Continuous Integration below), but a full `docker compose up`, "do all three containers actually reach `healthy` and serve real traffic together", is verified by hand during infrastructure-related issues (documented in each such issue's final report and, cumulatively, in `docs/deployment.md`), not by an automated recurring check.

---

## Test Stack

**Backend**: `pytest`, FastAPI's `TestClient` (route-level tests), a real PostgreSQL database, `moto` (mocked AWS S3), Ruff (lint + format, not a test tool but part of the same quality gate). Installed via `backend/requirements-dev.txt`: `pytest`, `httpx` (`TestClient`'s transitive dependency), `reportlab` (generates real PDF bytes for PDF-upload tests), `ruff`, `moto[s3]`.

**Frontend**: Vitest, jsdom (the DOM environment Vitest runs component tests in), React Testing Library, `@testing-library/user-event`, `@testing-library/jest-dom` (the `toBeInTheDocument()`-style matchers). Configured directly in `frontend/vite.config.ts`'s `test` block rather than a separate Vitest config file; see `docs/frontend.md`'s "Quality pipeline" section for the full tool configuration (ESLint, TypeScript, Prettier alongside it) and `src/test/setup.ts`'s own comments for the two jsdom polyfills it installs (`HTMLDialogElement`, `window.matchMedia`).

---

## Backend Testing

### Organization and naming conventions

Every backend test file lives directly under `backend/tests/`, one file per resource or concept, named `test_<thing>.py`. There is no subdirectory structure: flat, and small enough (24 files) that one doesn't help yet.

The naming convention distinguishes *what layer* a file tests, not just *what resource*:

- **Singular resource name = model/database-layer tests.** `test_analysis.py` and `test_medication_discrepancies.py` (an exception to the pattern in name only, still model-layer) construct SQLAlchemy model instances directly against the real test database and assert on constraints, defaults, relationships, and cascade behavior; no HTTP, no `TestClient`.
- **Plural resource name = route/API-layer tests.** `test_analyses.py`, `test_patients.py`, `test_medications.py`, `test_clinical_documents.py` drive the same resource through real HTTP requests via the `client` fixture, asserting on status codes and response bodies the way an actual API consumer would.
- **`test_<domain>_service.py` = service-layer tests.** `test_medication_reconciliation_service.py`, `test_analysis_result_service.py`, `test_clinical_document_service.py` call a service module's functions directly against the real test database, below the HTTP layer but above the raw model layer, the place business logic (not just persistence, not just routing) actually lives.
- **A few files test one specific cross-cutting concern directly**, independent of any one resource: `test_auth_login.py`/`test_auth_register.py` (the two auth endpoints), `test_users_me.py` (the authenticated-profile endpoint), `test_cors.py` (CORS middleware, built against its own throwaway FastAPI app rather than the real one; see `configure_cors`'s own docstring in `app/main.py`), `test_config.py` (`Settings` loading and defaults), `test_logging_config.py` (log formatters, the request-context filter, and the allowlist), `test_request_logging_middleware.py` (the request-logging middleware, via the real `client` fixture), `test_gemini_provider.py` and `test_ai_service.py` (the two layers of the AI integration; see "AI provider testing" below), `test_storage_service.py` (both storage backends; see "Storage testing" below), and `test_ai_prompts.py`/`test_medication_normalization.py` (pure functions, no database at all).
- **`test_analysis_workflow_integration.py`** is the one deliberate exception to "one file per resource or layer": a single end-to-end test spanning registration through analysis retrieval, kept in its own file specifically because it's a different *kind* of test (see "The testing pyramid" above), not a route test for a resource called "workflow."

### Fixtures and test database isolation

`tests/conftest.py` is the entire fixture setup: there's no factory library (no `factory_boy`, no `Faker`) and no separate fixtures directory; test data is built with plain Python literals or small per-file helper functions (see "Adding Tests" below).

Before `app` is ever imported, `conftest.py` rewrites the `DATABASE_URL` environment variable to point at a dedicated database, `medlens_test_db`, on the same local Postgres server the development database (`medlens_db`) lives on, and asserts that rewrite actually took effect (`assert _test_db_name in _test_database_url`) rather than trusting it silently. Because `Settings` and the SQLAlchemy engine are both constructed from environment variables at import time, this makes the *entire* application, including code paths that touch the database directly, not just ones reachable through a fixture, use the isolated test database automatically, with no dependency overrides needed to redirect it. `STORAGE_BACKEND` is forced to `local` and pointed at a fresh temp directory the same way, for the identical reason: a test run must never depend on, or write into, whatever a developer's own `backend/.env` happens to be configured for.

Three fixtures do the rest:

- **`_test_database`** (session-scoped, autouse): creates `medlens_test_db` if it doesn't already exist, then builds its schema from the SQLAlchemy models (`Base.metadata.create_all`). Runs once per test session.
- **`_clean_tables`** (function-scoped, autouse): deletes every row from every table, in reverse dependency order, after each test. This is what gives each test a clean slate without paying the cost of rebuilding the schema between every one of the 537 tests; nothing needs to opt into it.
- **`client`**: a plain `TestClient(app)`, freshly constructed per test.
- **`db`**: a plain `SessionLocal()`, for tests that touch the database directly (model- and service-layer tests) rather than through the API.

### Authentication testing

There's no shortcut for "log this test in as a user": every test that needs an authenticated user registers and logs in through the real `/auth/register` and `/auth/login` endpoints, the same as a real client would, via a small `_register_and_login(client, email, ...)` helper repeated (not shared/imported) across the test files that need it. This means JWT creation, password hashing, and the login endpoint's own correctness are exercised as a side effect of every other test that needs a token, not just by `test_auth_login.py`/`test_auth_register.py` directly. `test_users_me.py` and the `get_current_user` dependency it exercises additionally cover the negative space directly: missing, malformed, and expired tokens, and a validly-signed token referencing a user that no longer exists.

### API / route testing

Route-level tests use the `client` fixture end to end: a real HTTP request through `TestClient`, a real response, asserted on status code and JSON body. Current route prefixes (all nested under a patient where the resource belongs to one): `/auth/*`, `/users/me`, `/patients`, `/patients/{patient_id}/medications`, `/patients/{patient_id}/clinical-documents`, `/patients/{patient_id}/analyses`, `/analyses/recent`, `/health`. Every route test file covers, at minimum, the success path, validation failures (422s), authentication being required (401), and ownership isolation (a second registered user can never see or modify the first user's data, checked explicitly, not assumed).

### AI provider testing

Two distinct layers are tested separately, matching the actual code structure (`AIProvider` interface, `docs/design-decisions.md` Decision 15):

- **`test_gemini_provider.py`** tests `GeminiProvider` itself, with the underlying `google.genai.Client` mocked via `monkeypatch` (a `FakeClient`/`FakeModels` pair standing in for the real SDK), covering a missing API key failing before any client is constructed, a successful call, the JSON response-mime-type being requested, translation of both an SDK error and an unexpected exception into `AIProviderError`, rejection of an empty response, client reuse across calls, and, directly relevant to this project's logging work, that `duration_ms` and the failure `detail` field are logged on both the success and failure paths, and that the failure detail never leaks into the exception message returned to a caller.
- **`test_ai_service.py`** tests `AISummaryService` against a fake, in-memory `AIProvider` (never the real Gemini client at all, one layer further removed), covering prompt construction reaching the provider, response parsing into a validated `ClinicalSummary`, and every response-validation failure mode (malformed JSON, missing/incorrectly-typed fields, unexpected extra fields, an unexpected top-level structure) being rejected as `AIProviderError`.
- **One test, `test_summarize_uses_real_gemini_provider_by_default_when_key_missing`** (`test_analyses.py`), deliberately uses the *real*, non-mocked provider wiring: it exists specifically to prove the real dependency-injection path (not just the fake used everywhere else) fails gracefully (a `503`, not a crash) when no `GEMINI_API_KEY` is configured, which is also why CI never sets that secret (see Continuous Integration below).

### Evaluation runner testing

`backend/tests/test_evaluation_runner.py` tests `benchmark/runner/` (Issue #89; see `benchmark/README.md`), a top-level, non-application directory pulled into this suite the same way `test_benchmark_dataset.py` already is (an explicit `sys.path.insert()` for the repo root, since `benchmark/` sits alongside `backend/`, not inside it). No test in this file makes a real network call. Orchestration/parsing/failure-isolation behavior is exercised against a hand-written `FakeProvider` (no mocking library, the same convention as every other AI test above); a few tests construct the real `GeminiProvider`/`OpenBioLLMProvider`/`MedGemmaProvider` classes to check provider/generation metadata, but only inspect attributes; none of them call `generate_summary()`, so no client is ever built and no request is ever made. Covers: reuse of the real `benchmark.loader.load_cases` (no reimplementation), the identical-prompt guarantee (the same prompt string and hash reaching every selected provider for one case), `provider_response` preservation on both successful and failed parsing, the two-stage `invalid_json`/`schema_validation_error` classification, every entry in the failure taxonomy, that a `(case, provider)` failure never stops later pairs from running, the manifest's `"running"` → `"complete"`/`"interrupted"` lifecycle (including a simulated `KeyboardInterrupt`), output-directory collision refusal, `--providers`/`--cases`/`--tags` filtering (including their intersection and the zero-match failure case), the benchmark fingerprint's stability across formatting and sensitivity to real content changes, and that a configured secret never appears in a written artifact.

### Evaluation metrics testing

`backend/tests/test_evaluation_metrics.py` tests `benchmark/metrics/` (Issue #90; see `benchmark/README.md`'s "Scoring an evaluation run" section for the full methodology), pulled into this suite the same way as the two files above. No test makes a real network call or constructs an `AIProvider`: fixtures are hand-built `BenchmarkCase`/`PredictionResult` instances (the real #86/#89 dataclasses, never loaded from the actual `benchmark/cases/` dataset), so these tests are independent of its current content; one test also asserts, by reading the module source directly, that none of `benchmark/metrics/`'s files reference an `AIProvider` class at all. Covers: every medication-matching scenario (perfect match, false positive/negative, duplicate names resolved by dosage/route/frequency, duplicate names left deliberately ambiguous when those fields tie, reordered predictions producing an identical outcome, and confirming source_note/status/notes differences never influence which items are paired); every attribute null-handling combination (correct, incorrect, expected-null-hallucinated, expected-value-predicted-null, both-null) and `notes`'s four-way presence buckets and `source_note`'s correct/incorrect/null-prediction/excluded-ambiguous cases; the zero-denominator precision/recall/F1 convention (including a real zero-expected-medication vacuous case); micro/macro aggregation; `end_to_end` vs. `conditional_on_valid_output` (including a failed case with expected medications, and the documented zero-expected-medications-plus-failed-call interaction); every reliability rate; latency statistics excluding failed calls; `by_difficulty`/`by_tag` grouping and sample-size reporting; and the full artifact lifecycle (a complete run scoring successfully, and every fail-loud integrity check, incomplete status, fingerprint mismatch, duplicate records, unknown case ids, a provider with no predictions, an existing `metrics.json`, both refusing by default and succeeding under its explicit override flag). A separate script run against the real 30-case benchmark (self-matching each case's ground truth against itself) was used during development to confirm the matching algorithm handles every real duplicate-name group without error and produces exactly the audited set of ambiguous pairs, not re-run as part of the automated suite, since the synthetic fixtures above already cover the same logic deterministically.

### Evaluation report testing

`backend/tests/test_evaluation_report.py` tests `benchmark/report/` (Issue #91; see `benchmark/README.md`'s "Generating a comparison report" section and `docs/model-evaluation.md` for the methodology this tool presents), pulled into this suite the same way as the two files above. No test makes a real network call, calls an `AIProvider`, or reruns any benchmark case: fixtures are small, hand-built `BenchmarkCase`/`PredictionResult` instances written to real `tmp_path` run directories and scored with the real, unmodified `benchmark.metrics.cli.main`, so these tests exercise the actual #90 output shape #91 reads rather than a hand-guessed `metrics.json` fixture that could drift from it. Covers: provider-mapping parsing and citation ordering; every cross-run comparability check (`benchmark_fingerprint`/case-set/`prompt_hash` mismatches each raising, a `git_commit` mismatch only warning); that qualitative findings (`possible_inconsistencies`/`summary` excerpts) can never leak between two providers that share one source run, a regression test for a real bug caught in review; the "not applicable" suppression of precision, macro F1, and every difficulty/tag cell for a provider with zero evaluable cases, including a dedicated fixture that reproduces the exact reported symptom (a zero-evaluable provider's stored macro F1 and per-group F1 reading as a misleading nonzero value due to #90's own vacuous-credit convention on zero-expected-medication cases) before asserting the display-layer fix; that reliability numbers are never touched by any of that suppression; and an end-to-end CLI test confirming `report.md`/`figures/*.svg` are written correctly and no source run artifact is ever modified.

The five figures themselves (Matplotlib, `benchmark/report/charts.py`) are tested in two deliberately separate layers, matching the pure-data/rendering split the code itself keeps: `benchmark/report/chart_data.py`'s pure functions (no Matplotlib import at all) turn a provider's metrics into a plain, frozen spec, and are tested thoroughly, on ordering, exact values, which cells are "not applicable" versus a real 0%, provider-color assignment, tag-label humanization, and sample-size handling, all as fast, non-brittle assertions on plain data. `charts.py`'s own rendering functions get only thin smoke tests: that rendering completes, the output is well-formed SVG, and a handful of safety-critical substrings appear or don't (e.g. the literal "N/A" text for a suppressed value, and never a "0.0%" label in its place). Nothing asserts on Matplotlib's own internal SVG structure or pixel output, since that would be brittle across Matplotlib versions and isn't what determines correctness here.

### Storage testing

`test_storage_service.py` tests both `StorageService` implementations (Decision 21) with the same assertions run against each, so behavioral parity between them is checked directly rather than assumed: `LocalStorageService` against a real `tmp_path` (pytest's own temp-directory fixture), `S3StorageService` against `moto`'s `mock_aws()`, a real `boto3` client talking to a fully in-process fake AWS, never a real network call or real AWS account. Covers upload/download/delete round-tripping, `ObjectNotFoundError` for a missing key on both backends, that an uploaded S3 object is never made public (asserted against the actual ACL grants a mocked `get_object_acl` call returns, not just that `upload()` didn't raise), that a genuine S3-side failure raises `StorageError` and not `ObjectNotFoundError`, that AWS credentials never appear in a raised error message, and that storage failures and successful-upload timing are both logged with the right fields and never with file content.

### Migration testing

**No automated migration tests exist.** The test database's schema is built directly from the SQLAlchemy models (`Base.metadata.create_all(bind=engine)` in `conftest.py`), not by running Alembic migrations, so the test suite never actually executes a migration file, and a migration that's individually broken (doesn't match its own model change, doesn't apply cleanly to an existing database) would not be caught by `pytest -v`. What *does* verify a migration: `backend/Dockerfile`'s container startup runs `alembic upgrade head` before starting the server on every container start (Decision 19), so a broken migration fails a `docker compose up`/deployment immediately and visibly, and in practice every migration in this project has additionally been run by hand against a real development database while it was being written. This is a real, honestly-scoped gap, not an oversight this document is glossing over.

### Logging and timing metrics tests

`test_logging_config.py` tests the structured-logging machinery directly: `JSONFormatter`/`ConsoleFormatter` output shape, that a field not in the `ALLOWED_FIELDS` allowlist is silently dropped even if passed via `extra=` (the core security property the logging design rests on), and the request-context `ContextVar`/filter behavior. `test_request_logging_middleware.py` tests the middleware end to end through the real `client` fixture and pytest's `caplog` fixture: exactly one summary line per completed request, the right fields on it, `X-Request-ID` header behavior, and (via `caplog`, asserting on `record.<field>` attributes directly rather than parsing formatted text) that a realistic session, registering with a real password, uploading a real clinical document with realistic clinical text, never leaks any of it into a log line anywhere in the whole test run. Timing (`duration_ms`) is asserted the same way, spread across the files for whatever it's attached to: request timing in `test_request_logging_middleware.py`, AI provider timing in `test_gemini_provider.py`, storage timing in `test_storage_service.py`, analysis-duration and document-upload/extraction timing in `test_analyses.py`/`test_clinical_documents.py`.

### Middleware and CORS testing

`test_cors.py` is a deliberate exception to "test through the real `client` fixture": it builds its own minimal, throwaway `FastAPI()` app and calls `configure_cors` on it directly, so it can exercise multiple `app_env`/origin combinations in isolation without depending on (or accidentally being affected by) the rest of the real application's configuration. Covers the development-only localhost-regex allowance, that an untrusted origin's preflight is rejected with no CORS headers at all, and that production allows no origin (there is no cross-origin production request left to allow now that the frontend reaches the backend through nginx's own reverse proxy same-origin, Decision 24).

---

## Frontend Testing

See `docs/frontend.md`'s "Quality pipeline" section for the full tool configuration this section doesn't repeat (ESLint/TypeScript/Prettier setup, the jsdom polyfills in `src/test/setup.ts`, and why `test.globals` is deliberately off).

### Organization

Every frontend test file is co-located directly next to the source file it tests, named `<Thing>.test.tsx`/`<thing>.test.ts`, not a parallel `tests/` or `__tests__/` directory. A component's test lives beside the component; a hook's test lives beside the hook. This means the test suite's own directory shape mirrors `src/`'s: `api/`, `components/` (further split by feature area: `analyses/`, `common/`, `dashboard/`, `documents/`, `layout/`, `medications/`, `patients/`, `settings/`, `upload/`), `contexts/`, `hooks/`, `lib/`, `pages/`, `routes/`, `styles/`, `utils/`.

### Component testing

A component test renders the real component with React Testing Library's `render()` and asserts against what a user would actually see and do, `getByRole`, `getByLabelText`, `userEvent` clicks/typing, not against internal state or a shallow render tree. Where a component depends on a hook or the API layer, that dependency is mocked one layer below the component under test (see "API mocking" below), so a component test proves the component's own rendering and interaction logic, not the correctness of everything it happens to call.

### Page and route testing

Page tests (`src/pages/*.test.tsx`) render a page inside a `MemoryRouter` (React Router's in-memory router, for a test environment with no real browser URL) with whatever hooks it depends on mocked via `vi.mock()`, `useAuth`, `usePatients`, and similar, so a page test can drive every state a page can be in (loading, error, populated, empty) without a real backend anywhere in the loop. `src/routes/AppRoutes.test.tsx` is the one file that renders the *whole* route table at once, navigating between paths and asserting the right page/redirect happens: the wiring between routes, not any single page's own content, which the page tests already cover individually. `ProtectedRoute.test.tsx`/`PublicOnlyRoute.test.tsx` test the two route-guard components directly, in isolation from any specific page.

### Validation testing

Form validation logic is written as plain, exported functions (`medicationFormValidation.ts`, `patientFormValidation.ts`, `profileFormValidation.ts`, and the general-purpose helpers in `utils/validation.ts`), each tested directly by calling the function with representative inputs and asserting on its return value, no component, no rendering, no DOM at all. This is deliberate: validation rules are pure logic, and testing them as pure functions is both faster and a more direct test of the actual rule than driving them indirectly through a rendered form.

### API mocking

There is no network-level mocking (no MSW, no `nock`) anywhere in the frontend suite. Instead, `vi.mock('@/api/<module>', ...)` replaces the specific exported functions a hook or page actually calls with `vi.fn()` mocks, at the module boundary: `usePatients.test.ts` mocks `listPatients`/`archivePatient` from `@/api/patients`, for example, not any HTTP call underneath them. This mirrors the same layered-mocking principle used throughout the backend suite (mock at the boundary of the thing under test, not several layers below it): a hook test doesn't need to know or care that `listPatients` happens to be implemented with axios, only that it's an async function returning patients or rejecting with an `ApiError`. `src/api/client.test.ts` is the one file that tests the API layer itself, specifically `toApiError`, the function that normalizes an Axios error into this app's own `ApiError` shape, constructing fake `AxiosError` objects directly rather than making any real or mocked HTTP call.

### Provider testing

`AuthProvider.test.tsx` and `ThemeProvider.test.tsx` test the two React context providers directly: session/token persistence and restoration, the unauthorized-request handler wiring for `AuthProvider`; system-preference detection, persistence, and the token-application side effect for `ThemeProvider`; each with a small test component or `renderHook` consuming the context, rather than testing them only incidentally through whatever happens to consume them elsewhere.

### Accessibility in tests

There is no dedicated accessibility audit tool (`jest-axe`, `@axe-core/react`) in this project. What does exist: the majority of frontend test files (35 of the test files that touch rendered output) query rendered output through React Testing Library's semantic, role-based queries (`getByRole`, `findByRole`) rather than test IDs or CSS selectors, a query that can only succeed if the underlying markup already exposes the right accessible role and name, so these tests fail if a component's accessibility is regressed even though that was never their stated purpose. This is real, if partial and incidental, coverage, not a substitute for an automated audit, but not nothing either. See `docs/frontend.md`'s own "Accessibility" section for the accessibility *practices* this project follows in application code, separate from what's covered by tests specifically.

---

## Running Tests

### Backend

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt

ruff format --check .   # formatting, CI uses this exact form
ruff check .            # lint
pytest -v               # the test suite
```

The local PostgreSQL container must be running (`docker compose up --build` from `infra/`); tests connect to it at `localhost:5432`. `pytest.ini`'s `pythonpath = .` is what makes `from app... import ...` resolvable inside `tests/conftest.py` when pytest is invoked as the plain `pytest` command above, rather than `python -m pytest` (the two resolve `sys.path` differently; see the comment above `pythonpath = .` in `pytest.ini` for the full explanation).

Auto-fixable variants, for local iteration (not what CI runs):

```bash
ruff check . --fix      # lint, auto-fixing what's safely fixable
ruff format .            # format in place
```

### Frontend

```bash
cd frontend
npm run lint            # ESLint
npm run typecheck       # TypeScript, strict, no emit
npm run format:check    # Prettier, fails if any file isn't already formatted
npm run test            # Vitest
npm run build           # tsc -b && vite build, the final, authoritative check
```

`npm run lint:fix` and `npm run format` apply the auto-fixable subset of the first two, for local iteration.

---

## Continuous Integration

Two independent GitHub Actions workflows, each triggered only by changes to its own half of the codebase (`backend/**`/`frontend/**` respectively, or the workflow file itself): a frontend-only change never runs the backend workflow and vice versa:

- **`.github/workflows/backend.yml`**: a single `ubuntu-latest` job against a real `postgres:16` service container (same image and credentials as local dev), running `pip install -r requirements-dev.txt`, then `ruff format --check .`, `ruff check .`, `pytest -v`, in that order, the exact commands documented above, never invoked differently, from a `backend/` working directory (so this never lints or formats `benchmark/`, only tests it indirectly via `backend/tests/test_benchmark_dataset.py`/`test_evaluation_runner.py`). `DATABASE_URL`/`JWT_SECRET_KEY` are set directly in the job's `env:` block (neither is a real secret in this throwaway context); `GEMINI_API_KEY` is deliberately never set, which is exactly the condition `test_summarize_uses_real_gemini_provider_by_default_when_key_missing` needs (see "AI provider testing" above): GitHub Actions never injects a secret into a job unless a step explicitly references it, so simply not referencing it is sufficient, no extra handling required. This workflow's trigger path filter also includes `benchmark/**` (Issue #89), alongside `backend/**`; without it, a change to the top-level `benchmark/` directory alone (the dataset or the evaluation runner) would never run the one job whose tests actually exercise it.
- **`.github/workflows/frontend.yml`**: the mirror image for the frontend: `npm ci`, then `npm run lint`, `npm run typecheck`, `npm run format:check`, `npm test`, `npm run build`, in that order, the exact `package.json` scripts documented above.

Both workflows end with a Docker image build step (`docker/build-push-action`, cached via GitHub's own Actions cache, Decision 23), proving the production image for that half of the app still builds, after every other check has already passed. Neither workflow runs the built image or exercises `docker compose up`; see "What is not tested" above for why that's a manual verification step instead.

**Expected workflow before opening a PR**: run the relevant commands above locally (backend commands if `backend/` changed, frontend commands if `frontend/` changed, both if both did) and confirm they all pass. A red check on a PR always reproduces locally with the exact command named in that failed step's log: there is no CI-only configuration or behavior that could pass locally and fail in CI, or vice versa, by design.

---

## Adding Tests

### Where new tests belong

**Backend**: a new file in `backend/tests/`, following the existing naming convention (see "Organization and naming conventions" above): `test_<resource>.py` for a new model (singular) or a new set of routes (plural), `test_<domain>_service.py` for new service-layer logic, or a new test function in an existing file if the new behavior belongs to a resource/concept that already has one. There is no `__init__.py`, no subdirectory structure to place a file into: `pytest.ini`'s `testpaths = tests` already finds every `test_*.py` file directly under `tests/`.

**Frontend**: a `<Thing>.test.tsx`/`.test.ts` file directly beside the source file it tests, never a separate test directory. A new component gets a test beside it; a new hook gets a test beside it; new validation logic gets a test beside the function, not the component that happens to call it first.

### Naming conventions

Backend: `test_<what_is_being_verified>` in `snake_case`, descriptive enough to read as a sentence on its own in a test report (`test_delete_document_returns_404_for_another_users_patient`, not `test_delete_2`). Frontend: a `describe('ComponentOrHookName', ...)` block per file matching the thing under test, with `it('does something specific', ...)` descriptions in the same descriptive-sentence style.

### Patterns already used throughout the repository

- **Real dependencies over mocks, wherever practical**: a real Postgres database (backend), real rendered components (frontend), reserving mocks specifically for genuine external boundaries: an SDK client (Gemini), a cloud API (S3, via `moto`), or a sibling module one layer below the thing actually under test (frontend's `vi.mock('@/api/...')`).
- **Small, per-file helper functions instead of a shared test-utilities module**: `_register_and_login(client, email, ...)` is repeated, not imported, across every backend test file that needs an authenticated user; `renderLoginPage()`/`renderAt(path)`-style local render helpers are similarly local to the frontend test file that needs them. Deliberately not centralized; see any recent test file's own comments for the reasoning pattern this project applies broadly (a small amount of duplication that keeps each test file self-contained beats a shared utility that couples files together).
- **Assert on structured data, not formatted text**: `caplog`-based backend tests assert on `record.<field>` attributes directly (`record.event == "login_succeeded"`), never by parsing or substring-matching a formatted log line; frontend tests assert on rendered, accessible output (`getByRole('button', { name: '...' })`), never on raw HTML strings.
- **Cover the negative space, not just the success path**: every route test file covers authentication being required, ownership isolation between users, and the specific validation failures that endpoint can produce, alongside its success path.
- **Verify security-relevant properties directly, not just "it didn't crash"**: e.g. the logging allowlist test asserting a disallowed field is actually absent from formatter output, not merely that formatting didn't raise; the S3 ACL test asserting the actual grants returned by a mocked `get_object_acl` call, not just that `upload()` succeeded.

---

## Coverage

No coverage percentages are collected or reported anywhere in this project (no `pytest-cov`, no `nyc`/`c8`, no coverage tooling of any kind configured on either side); the summary below is a qualitative description of the actual test files that exist, not a number.

**Extensively tested**: authentication (registration, login, JWT validation, session behavior on both sides), patient/medication/clinical-document CRUD and ownership isolation, the medication reconciliation engine (normalization, every discrepancy rule, full orchestration), the analysis lifecycle (creation, persistence, retrieval, deletion, the complete integration workflow), structured logging (formatting, the field allowlist, sensitive-data omission, request tracing), and both storage backends. On the frontend: form validation logic, the hooks layer (one file per hook, covering loading/error/success/retry states), and the great majority of components and pages.

**Moderately tested**: timing metrics (`duration_ms`), covered on the specific events it's attached to, but not exhaustively cross-checked against every event that logs a duration; CORS/development-only behavior (a handful of targeted tests against an isolated app, not exercised through the full application stack); the frontend route table as a whole (one file, `AppRoutes.test.tsx`, covering the major navigation paths rather than every possible route combination).

**Minimally tested or not tested at all**: database migrations (no automated tests at all; see "Migration testing" above), Docker Compose / full-stack deployment behavior (validated by hand during infrastructure issues, not by an automated recurring test), accessibility (no dedicated audit tool; partial, incidental coverage via RTL's role-based queries only), end-to-end browser flows (no Playwright/Cypress on either side), and load/performance characteristics (timing is logged, not asserted against a budget).
