# Testing

There are two suites:

- **Backend:** `pytest`, about 537 tests, run against a real isolated PostgreSQL database
- **Frontend:** Vitest + React Testing Library, about 600 tests

Tests ship in the same change as the feature they cover.

## Running

```bash
# Backend (needs local Postgres running: `docker compose up` in infra/)
cd backend
pip install -r requirements-dev.txt
ruff format --check . && ruff check . && pytest -v

# Frontend
cd frontend
npm run lint && npm run typecheck && npm run format:check && npm test && npm run build
```

Auto-fix commands: `ruff check . --fix`, `ruff format .`, `npm run lint:fix`, `npm run format`.

CI runs exactly these commands, so a red check always reproduces locally.

## Backend

### Layout and naming

Files live flat in `backend/tests/`. The name tells you the layer:

| Pattern | Layer |
|---|---|
| `test_analysis.py` (singular) | Model and DB constraints |
| `test_analyses.py` (plural) | HTTP routes via `TestClient` |
| `test_<domain>_service.py` | Service functions called directly |
| `test_analysis_workflow_integration.py` | One end-to-end test from register to analysis |

Cross-cutting files cover auth, config, CORS (using its own throwaway app), logging, middleware, AI providers, storage, prompts, normalization, and the benchmark tooling.

### Database isolation

`conftest.py` rewrites `DATABASE_URL` to `medlens_test_db` **before importing the app**, so all code uses the test database. It also forces `STORAGE_BACKEND=local` in a temp directory. Decision 27 explains why tests use real Postgres instead of mocks or SQLite.

- `_test_database` (session scope): creates the DB and runs `Base.metadata.create_all`
- `_clean_tables` (autouse): deletes all rows after each test
- `client` (`TestClient(app)`) and `db` (`SessionLocal()`)

There are no factories or Faker. Tests authenticate through the real register and login endpoints using a per-file `_register_and_login` helper.

### What every route file covers

The success path, 422 validation errors, 401 without a token, and **ownership isolation** (a second user can't see or modify the first user's data).

### External boundaries

No test makes a network call.

- **AI:** Gemini's `genai.Client` and Ollama's `urlopen` are monkeypatched. The service layer uses a `FakeProvider`. Routes use `dependency_overrides`. One test deliberately uses the real wiring with no `GEMINI_API_KEY` and expects a 503, which is why CI never sets that key. See [ai.md](ai.md#testing).
- **Storage:** both backends run the same assertions (local against `tmp_path`, S3 against `moto`). Tests also check that S3 ACL grants are private and that credentials never appear in error messages.
- **Logging:** tests check that fields outside the allowlist are dropped, and that a realistic session (real password, real document text) leaks nothing. Assertions use `caplog` `record.<field>`, not formatted strings.

### Benchmark tooling

`test_evaluation_runner.py`, `test_evaluation_metrics.py`, and `test_evaluation_report.py` test `benchmark/` (imported via `sys.path`) using hand-built cases and fake providers. They cover:

- Identical prompts across providers
- The failure taxonomy and per-pair isolation
- Manifest lifecycle and integrity checks
- Matching and attribute edge cases, and zero-denominator conventions
- Cross-run comparability
- "Not applicable" suppression for providers with zero evaluable cases

Chart *data* is tested thoroughly. Chart *rendering* only gets smoke tests.

## Frontend

- Tests sit next to their source: `Thing.tsx` and `Thing.test.tsx`.
- Components render for real and are queried by role or label, then driven with `userEvent`.
- **Mocking happens one layer down:** hook tests mock `@/api/*` functions, and page tests mock hooks. There's no MSW. `client.test.ts` tests `toApiError` directly.
- Pages render in a `MemoryRouter`. `AppRoutes.test.tsx` covers the route table as a whole.
- Validation functions are tested as pure functions.
- `src/test/setup.ts` polyfills `<dialog>` and `matchMedia` for jsdom.

## Conventions

- Prefer real dependencies. Mock only true external boundaries or the layer directly below the code under test.
- Keep helpers local to each file rather than in a shared test-utils module.
- Assert on structured data and accessible output, not formatted text.
- Test security properties directly (for example, that a field is *absent*, or that an ACL grant is private).
- Name tests descriptively, e.g. `test_delete_document_returns_404_for_another_users_patient`.

## Known Gaps

- **No E2E browser tests** (Playwright or Cypress)
- **No migration tests:** the schema comes from `create_all`. Migrations are only exercised by `alembic upgrade head` on container start.
- **No accessibility audit tool:** role-based queries give partial coverage incidentally.
- **No load or performance tests:** timing is logged but not asserted.
- **No automated `docker compose up` check:** CI only builds the images.
- **No coverage metrics** are collected.
