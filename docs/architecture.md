# Architecture

## Overview

MedLens follows a modern three-tier web architecture consisting of a React frontend, FastAPI backend, PostgreSQL database, and external AI service integration.

The application is designed around a clinical documentation reconciliation workflow. Users upload multiple synthetic clinical documents, the backend orchestrates AI-powered medication extraction and normalization, and a reconciliation engine compares medication information across documentation sources to identify potential documentation inconsistencies.

The frontend provides the user interface, the backend manages application logic and AI orchestration, PostgreSQL stores application data, and the AI service performs structured information extraction.

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

- Docker
- Docker Compose
- GitHub Actions
- AWS EC2
- AWS S3 (future)

---

## High-Level Architecture

```text
                    User
                      │
                      ▼
         React + TypeScript Frontend
                      │
               REST API (HTTPS)
                      │
                      ▼
               FastAPI Backend
                      │
      ┌───────────────┼────────────────┐
      ▼               ▼                ▼
 PostgreSQL      Gemini API    Reconciliation Engine
```

---

## System Components

### Frontend

Responsible for:

- User authentication
- Document upload
- Dashboard
- Viewing uploaded clinical documents
- Displaying reconciliation results
- Reviewing discrepancy reports

---

### Backend

Responsible for:

- Authentication
- API endpoints
- Business logic
- Document management
- AI orchestration
- Medication normalization
- Reconciliation workflow
- Database communication

---

### Database

Stores:

- Users
- Clinical Documents
- Medication Mentions
- Medications
- Analyses
- Medication Discrepancies
- Analysis Medication Mentions
- Analysis Inconsistencies

---

### AI Service

Responsible for:

- Medication extraction
- Dosage extraction
- Frequency extraction
- Medication normalization assistance
- Clinical note summarization
- Structured JSON generation

---

### Reconciliation Engine

Implemented as a deterministic backend service, not an AI component. Given a patient and a set of clinical documents, it:

- Validates that every selected document exists and belongs to that patient, reusing the same validation as analysis creation.
- Loads the patient's current Medication records and the MedicationMention records extracted from the selected documents.
- Normalizes medication names and comparable fields (dose, route, frequency, status) using fixed rules: trimming, lowercasing, whitespace collapsing, and a small set of explicit aliases such as PO to oral and QD to daily. No fuzzy matching, brand-to-generic inference, or semantic matching is performed.
- Applies a fixed set of comparison rules to produce MedicationDiscrepancy records, each with a deterministic title, explanation, expected value, and observed value.
- Assigns severity from a single, centralized mapping from discrepancy type to severity.

AI is responsible only for producing the medication data the reconciliation engine reads. The comparison logic itself never calls an AI provider, so its output is reproducible and directly testable.

As of Issue #148, this engine is invoked automatically as part of analysis creation - see the pipeline below and "Analysis Creation Pipeline" under Expected Data Flow. `run_medication_reconciliation` (`app/services/medication_reconciliation_service.py`) remains a second, independent entry point into the same engine: given a patient and a set of clinical document ids, it creates its own Analysis, queries `MedicationMention` rows already persisted against those documents (rather than bridging AI-extracted ones), and completes or fails that Analysis on its own. Nothing in this issue changed that function's behavior or its own callers (there are none in the API today) - the shared logic it always used (`build_discrepancy_findings`, `create_medication_discrepancies`, severity counting) was extracted into a `reconcile_medications` helper so the AI-summary flow described below could reuse the exact same engine rather than duplicating it.

---

## Expected Data Flow

The expected application workflow is:

1. User logs in.
2. User uploads one or more synthetic clinical documents, or selects existing ones (Issue #145).
3. Backend validates the selected documents.
4. Documents are stored in PostgreSQL (if newly uploaded).
5. Backend sends document text to the AI service.
6. AI returns structured medication information as JSON.
7. Backend validates the AI response using Pydantic models.
8. Medication reconciliation runs automatically against the patient's medication list.
9. Medication discrepancies and their supporting evidence are persisted.
10. Analysis is marked completed.
11. The frontend displays the AI summary and reconciliation findings on the Analysis Results page.

### Analysis Creation Pipeline (Issue #148)

`POST /patients/{patient_id}/analyses` (`summarize_clinical_documents`, `app/api/routes/analyses.py`) is the single entry point covering the whole pipeline end to end:

```text
Clinical Documents
        ↓
Medication Extraction       AISummaryService.summarize() → ClinicalSummary.medications
        ↓
Medication Reconciliation   reconcile_ai_extracted_medications() → reconcile_medications()
        ↓
Persist Findings            MedicationMention + MedicationDiscrepancy rows
        ↓
Analysis Completed          mark_analysis_completed() with real severity counts
        ↓
Analysis Results            GET .../analyses/{analysis_id} → AnalysisDetailPage
```

`persist_analysis_result` (`app/services/analysis_result_service.py`) owns the middle three steps. After staging `AnalysisMedicationMention`/`AnalysisInconsistency` rows exactly as before, it now calls `reconcile_ai_extracted_medications` (`app/services/medication_reconciliation_service.py`), which:

- Persists each AI-extracted medication as a real `MedicationMention`, attached to its true source document (Issue #152). The AI's prompt numbers each note it is given ("Note 1", "Note 2", ...; see `app/ai/prompts.py`), and its response now reports which numbered note each medication came from (`Medication.source_note`, `app/ai/schemas.py`); `_resolve_source_document_id` (`medication_reconciliation_service.py`) maps that number back to the real document at that position in `ordered_clinical_documents` (`analysis_service.py`) - the same deterministic, id-ascending order used to build the prompt in the first place, so the numbering stays reproducible between the two call sites. A medication mentioned in more than one selected document is expected to appear as more than one entry in the AI's response (one per note it was found in), becoming one correctly-attributed `MedicationMention` per document. If the AI omits `source_note` or reports a number outside the range of selected documents, attribution falls back to the selected document with the lowest id - the same placeholder Issue #148 always used, now scoped to just that malformed-response edge case rather than applied unconditionally. Historical analyses created before Issue #152 keep whichever (possibly inexact) document they were attached to at the time; this cannot be corrected retroactively since the original note-to-medication attribution isn't recoverable after the fact.
- Queries the patient's `Medication` list (scoped by `patient_id`, same as `run_medication_reconciliation`) and calls the shared `reconcile_medications` helper, which runs the unchanged `build_discrepancy_findings` and persists results via the unchanged `create_medication_discrepancies` - both reused exactly as `run_medication_reconciliation` always used them, just shared through one function instead of two copies.
- Returns real severity counts, which `persist_analysis_result` now passes into `AnalysisCompletedSummary` instead of the hardcoded zeros used before this issue.

Everything reconciliation stages (the bridged `MedicationMention` rows, the `MedicationDiscrepancy` rows) is added to the session but not committed until `mark_analysis_completed`'s own `db.commit()` - the same staging pattern `persist_analysis_result` already used for `AnalysisMedicationMention`/`AnalysisInconsistency`. If reconciliation raises for any reason, the route's existing outer `try`/`except` (unchanged) rolls back the whole transaction and marks the analysis `failed` with the same sanitized error handling every other failure in this endpoint already uses - so a reconciliation failure can never leave a completed analysis with partially persisted discrepancies, and never requires new error-handling code.

`GET /patients/{patient_id}/analyses/{analysis_id}` now also returns `medication_discrepancies` (see `docs/api.md`), which `AnalysisDetailPage` renders directly - real findings, not a placeholder, once reconciliation has actually run for that analysis.

---

## Data Model

Every clinical resource is owned through `Patient`, not directly by `User` - see `docs/data-model.md` for the full entity reference and the Sprint 3.5 migration that got the schema here.

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

- JWT authentication
- Password hashing
- Protected API routes
- Environment variables for secrets
- Input validation
- Structured AI response validation
- Secure database connections

Only synthetic clinical data is used throughout the application.

---

## Future Architecture Improvements

Potential future additions include:

- Background processing using Celery or FastAPI Background Tasks
- Redis caching
- AWS S3 document storage
- CloudWatch logging
- Kubernetes deployment
- Distributed tracing
- Sentry monitoring
- FHIR integration
- RxNorm integration

---

## Design Principles

The architecture follows several guiding principles:

- AI is a component of the system, not the product itself.
- Business logic remains deterministic whenever possible.
- Clinical documents serve as the primary source of information.
- AI extracts structured data rather than making clinical decisions.
- Users remain responsible for reviewing all identified discrepancies.
- Every AI-generated discrepancy should include supporting evidence from the original documentation.

---

## Notes

This document represents the intended system architecture for MedLens and will evolve as the project is implemented. As new features are introduced, the architecture documentation will be updated to reflect significant design decisions and implementation changes.