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
- **Medication reconciliation service**: each supported discrepancy rule in isolation, including the discontinued-status case taking precedence over the general status conflict, no finding when only one side has a comparable value, no finding for values that are equivalent after normalization, deduplication of identical mentions into a single finding, separate findings for genuinely distinct conflicting values, correct linkage to the originating Medication and MedicationMention, the centralized severity mapping, full orchestration through `run_medication_reconciliation` including status and timestamp progression, count totals, provider and model metadata, rejection of a nonexistent or another user's document, a selected document with no mentions completing successfully, rollback of staged discrepancies and a sanitized error message on an unexpected failure, and isolation from another user's medications.
- **Configuration** — application settings load expected values from environment variables and fall back to documented defaults when optional values are not set.

---

## Future Testing

- AI integration
- Frontend (Vitest and React Testing Library)
- CI/CD (running the backend test suite automatically on pull requests via GitHub Actions)
