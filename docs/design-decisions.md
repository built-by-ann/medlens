# Design Decisions

Significant architectural choices and their trade-offs. Numbers are stable because other docs reference them.

## Foundations

**1. FastAPI over Flask.** Built-in validation, OpenAPI docs, and Pydantic typing. *Cost:* a smaller ecosystem.

**2. PostgreSQL over MongoDB.** The data is highly relational (users → patients → documents, medications, analyses). *Cost:* schema migrations.

**3. React + TypeScript.** Compile-time checking catches wrong prop shapes and field typos. *Cost:* a build step and annotation overhead.

**4. Docker Compose everywhere.** One `infra/docker-compose.yml` for local and production, so there is no separate "how prod runs" to maintain. *Cost:* Docker is a prerequisite, and some changes need a rebuild.

**7. Service-oriented backend.** Routes handle HTTP; services hold the business logic. Services can be tested without an HTTP layer. *Cost:* extra indirection, and nothing mechanically stops a route from reaching into the DB. Decision 17 is the deliberate exception.

**8. Synthetic data only.** This is a portfolio app, so it carries no HIPAA scope. *Cost:* synthetic notes are cleaner than real ones. This is a permanent boundary, not a temporary one.

**9. Issue-driven workflow.** Every change goes through GitHub issues, feature branches, and PRs, so each change is traceable. *Cost:* process overhead for a single contributor.

## AI

**5. Structured AI output.** The model returns one JSON object (`medications`, `possible_inconsistencies`, `summary`) instead of prose, so downstream code consumes fields directly. *Cost:* observations that don't fit a field are lost.

**6 / 16. AI output is untrusted and validated strictly.** Responses are parsed with `ClinicalSummary.model_validate_json` using `extra="forbid"`. Malformed JSON and schema mismatches both become `AIProviderError`. Rejecting unknown fields catches the model drifting from the prompt contract. *Cost:* harmless additive fields are also rejected, and the prompt and schema are kept in sync by hand.

**12. Deterministic reconciliation.** AI extracts mentions. Comparing structured records is plain code using fixed normalization and an explicit alias list, with no fuzzy matching or LLM. The result is reproducible, unit-testable, and can't silently merge different drugs. *Cost:* brand vs. generic names aren't matched unless an alias is added.

**13. Narrow rule for `unsupported_medication_list_entry`.** This finding only fires when a selected document is a `medication_list` or `medication_reconciliation_form`. A visit note's silence about a drug proves nothing. *Cost:* the rule produces no findings for analyses built only from notes, and it depends on accurate document types.

**15. `AIProvider` abstraction.** There is one method (`generate_summary(prompt) -> str`) and one exception type. Each provider is the only class that imports its SDK. The design was proven three times: OpenBioLLM via HF text completion, MedGemma via HF chat completion, then both rewritten to call local Ollama. Nothing above the interface changed. *Cost:* the interface flattens richer provider capabilities to string in, string out.

**17. The analyses route orchestrates persistence.** `AISummaryService` only validates. `persist_analysis_result` only stores. The route sequences the two, so the AI service stays testable without a database. *Cost:* this route is thicker than the others.

**20. Provider failure detail is logged but never returned.** Gemini's `APIError.message` is logged as `detail` so failures like a retired model are diagnosable. It is kept out of the 503 response so provider internals aren't exposed to users. A test asserts the two never match.

## Data

**10. `ON DELETE SET NULL` on discrepancy foreign keys.** A finding records what was true at analysis time. It should survive deletion of its medication or mention, and deleting a finding should never cascade to clinical data. This is the only database-level `ON DELETE` action outside the association table.

**11. `analysis_clinical_documents` association table.** Analyses and documents are many-to-many. The table uses a composite primary key (no surrogate id) and `ON DELETE CASCADE` on both sides, because a link row has no meaning of its own.

**14. Two-phase commit for analysis runs.** `pending` and `processing` are each committed on their own. Discrepancies and the final `completed`/`failed` state commit together. A failed run therefore always leaves a record, and a completed run never has partial findings. *Cost:* observers can briefly see a `processing` analysis with no findings.

**21. Pluggable `StorageService`.** The interface is upload, download, and delete, with `Local` and `S3` implementations selected by `STORAGE_BACKEND`, mirroring the AI provider pattern. S3 configuration is validated at startup. Local development and tests never touch AWS (S3 tests use `moto`). *Cost:* keeping two implementations behaviorally consistent relies on a shared test suite.

## Security and Auth

**26. Stateless JWT with ownership-based authorization and no roles.** Every user is a symmetric provider, so authorization is just "does this resource belong to you". That check lives in `get_current_user` and `get_owned_patient`. A resource that isn't yours returns 404, not 403, to prevent id enumeration. *Cost:* no early token revocation (30-minute expiry), and no path to shared patients without a redesign.

**22. Central structured logging with a field allowlist.** `app/core/logging_config.py` configures the root logger once. Fields not in `ALLOWED_FIELDS` are dropped, so an accidental `extra={"raw_response": ...}` fails safe. A denylist would only block names it already knows about. `user_id` travels via `request.state` instead of a ContextVar, because sync dependencies run in copied contexts.

## Infrastructure

**18. Multi-stage, non-root Dockerfiles with `.dockerignore`.** The original `COPY . .` would have baked `backend/.env` secrets into an image layer, so `.dockerignore` is treated as a security fix. The backend runs as `appuser`. The frontend is served by `nginx:alpine` rather than Vite preview or Node. *Cost:* `VITE_API_BASE_URL` and `DOMAIN` are build args.

**19. Migrations run on every backend start.** `CMD` runs `alembic upgrade head` before uvicorn. `alembic/env.py` reads `DATABASE_URL`. A forgotten manual step had caused `relation "users" does not exist` on a fresh database. *Cost:* this is unsafe for multiple replicas, and a failed migration blocks startup.

**23. BuildKit cache mounts and the GHA cache.** Cache mounts keep pip and npm downloads out of image layers (replacing `--no-cache-dir`) while persisting them between builds. `type=gha` makes that persistence work in CI. *Cost:* requires BuildKit, and GHA cache eviction still causes occasional full rebuilds.

**24. Same-origin deployment via an nginx reverse proxy.** `/api/*` is proxied to the backend, and the backend port binds to `127.0.0.1`. This removes the public backend port, the build-time hostname, and production CORS. CORS stays only for `npm run dev`. nginx resolves `backend` per request (Docker DNS `127.0.0.11`), so a recreated backend keeps working and the frontend needs no `depends_on`. Forwarded headers plus `--forwarded-allow-ips='*'` preserve real client IPs, which is safe because only nginx can reach the backend.

**25. Dummy-certificate bootstrap and on-demand certbot.** `ensure-dummy-cert.sh` writes a self-signed certificate when none exists, so the same Compose file works in every environment. Certbot sits behind a Compose profile, and renewal is a host cron job. `DOMAIN` is a build arg rather than `envsubst`, which would clobber nginx's own `$host`. *Cost:* a browser warning until a real certificate is issued, `DOMAIN` must match the certbot `-d` flag, and the cron job lives outside version control.

## Testing

**27. Real PostgreSQL for tests, not mocks or SQLite.** Database-level behavior like `SET NULL` only fires on real Postgres. `conftest.py` points `DATABASE_URL` at `medlens_test_db` before importing the app. *Cost:* Postgres is required to run tests, and the schema comes from `create_all`, so migration files aren't exercised.

## Future

Background jobs, caching, monitoring, and performance work will be recorded here when they happen.
