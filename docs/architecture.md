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
- Analyses
- Medication Discrepancies

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

Responsible for:

- Comparing medication information across multiple clinical documents
- Detecting documentation inconsistencies
- Generating discrepancy explanations
- Producing evidence-backed reconciliation reports

The reconciliation engine combines AI-generated structured data with application business logic. Rather than relying solely on AI, MedLens performs deterministic comparisons between extracted medication information to identify potential documentation inconsistencies.

---

## Expected Data Flow

The expected application workflow is:

1. User logs in.
2. User uploads one or more synthetic clinical documents.
3. Backend validates the uploaded documents.
4. Documents are stored in PostgreSQL.
5. Backend sends document text to the AI service.
6. AI returns structured medication information as JSON.
7. Backend validates the AI response using Pydantic models.
8. Medication names and statuses are normalized.
9. The reconciliation engine compares medication information across selected documents.
10. Potential documentation inconsistencies are identified.
11. Analysis results are stored in PostgreSQL.
12. The frontend displays discrepancy reports with supporting evidence.

---

## Data Model

```text
User
 │
 ├── ClinicalDocument
 │      └── MedicationMention
 │
 └── Analysis
        └── MedicationDiscrepancy
```

### Relationships

```text
User
 1 ─── many ClinicalDocument

ClinicalDocument
 1 ─── many MedicationMention

User
 1 ─── many Analysis

Analysis
 1 ─── many MedicationDiscrepancy
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