# MedLens

An AI-powered clinical documentation reconciliation platform that extracts medication information from multiple clinical documents, identifies potential documentation inconsistencies, and demonstrates production-grade software engineering practices.

**Status:** Active Development (Sprint 2)

---

# Overview

MedLens is a full-stack AI application inspired by research conducted at Vanderbilt University Medical Center on medication documentation inconsistencies within electronic health records.

Users can securely authenticate, upload synthetic clinical documents by pasting text or uploading TXT and PDF files, and prepare them for AI-powered medication reconciliation and discrepancy analysis.

The application allows users to upload multiple synthetic clinical documents—including medication lists, visit notes, discharge summaries, progress notes, and medication reconciliation forms. AI extracts structured medication information from each document, compares information across documentation sources, and highlights potential medication reconciliation issues with evidence supporting each finding.

The AI layer is designed around a provider-agnostic architecture that supports multiple large language models through a common interface. This enables MedLens to evaluate and compare both general-purpose and domain-specific medical LLMs while maintaining the same reconciliation workflow.

Rather than functioning as an AI chatbot, MedLens demonstrates how large language models can be integrated into a realistic clinical documentation workflow through a production-style software architecture.

The project is built to showcase modern software engineering practices, including full-stack development, cloud deployment, containerization, automated testing, CI/CD, modular AI integration, and scalable backend architecture.

---

# Motivation

Medication information often exists in multiple locations throughout a patient's healthcare record. A medication may appear in a medication list, visit note, discharge summary, or medication reconciliation document, and these sources do not always remain consistent over time.

During research at Vanderbilt University Medical Center, I studied medication documentation inconsistencies within electronic health records. MedLens was inspired by that work and explores how AI can assist by extracting medication information from multiple clinical documents, comparing documentation sources, and surfacing potential reconciliation issues for human review.

The application uses **synthetic clinical data only** and is intended solely for educational and portfolio purposes.

---

# How It Works

1. Register and authenticate using JWT.
2. Upload one or more synthetic clinical documents by:
   - Pasting document text
   - Uploading `.txt` files
   - Uploading PDF files
3. PDF documents are parsed and text is extracted.
4. Clinical documents are securely stored and associated with the authenticated user.
5. AI extracts structured medication information using schema-constrained JSON outputs.
6. Medication names and statuses are normalized into a consistent format.
7. MedLens compares medication information across documentation sources.
8. Potential medication documentation inconsistencies are identified.
9. Evidence-backed discrepancy reports are generated for human review.
10. Completed analyses are saved for future reference.

---

# Current Features

## Authentication

Completed:

- User registration
- User login
- JWT authentication
- Protected API endpoints

---

## Clinical Documents

Implemented:

- Paste document text
- Upload `.txt` files
- Upload PDF files
- View uploaded clinical documents
- View individual clinical documents
- Delete uploaded clinical documents

Planned:

- Dashboard document management
- Bulk document uploads

---

## AI Medication Extraction

The application will:

- Extract medication names
- Extract dosage information
- Extract medication frequency
- Extract medication route
- Infer medication status
- Normalize medication terminology
- Preserve supporting context from the source document
- Validate structured JSON outputs

---

## Reconciliation Analysis

Users will be able to:

- Compare medication information across multiple documentation sources
- Detect medication documentation inconsistencies
- View evidence supporting each discrepancy
- Review AI-generated explanations
- Save completed reconciliation analyses

---

## Dashboard

Users will be able to:

- View uploaded clinical documents
- Review previous analyses
- Search saved analyses
- Review discrepancy reports
- Delete saved analyses

---

# Technology Stack

## Frontend

- React
- TypeScript
- Vite
- React Router

## Backend

- FastAPI
- Python
- SQLAlchemy
- Alembic
- Pydantic
- JWT Authentication

## Database

- PostgreSQL

## AI

The application uses a modular AI layer that supports multiple language model providers through a common interface.

Current provider:

- Google Gemini

Planned providers:

- OpenBioLLM
- MedGemma

The backend is designed so multiple providers can be evaluated using the same extraction pipeline, prompts, and validation logic.

## Infrastructure

- Docker
- Docker Compose
- GitHub Actions (planned)
- AWS EC2 (planned)
- AWS S3 (planned)

## Testing

- pytest
- End-to-end API testing
- Authentication tests
- Clinical document CRUD tests
- File upload tests
- Vitest (planned)
- React Testing Library (planned)
- Playwright (planned)

---

# Architecture

```text
                    User
                      │
                      ▼
         React + TypeScript Frontend
                      │
            Upload Clinical Documents
                      │
                      ▼
               FastAPI Backend
                      │
              Business Services
                      │
      ┌───────────────┼────────────────┐
      ▼               ▼                ▼
 PostgreSQL      AI Service      Reconciliation Engine
                      │
              LLM Provider Layer
      ┌───────────────┼────────────────┐
      ▼               ▼                ▼
   Gemini        OpenBioLLM       MedGemma
                      │
                      ▼
     Structured Medication Extraction
                      │
                      ▼
        Medication Discrepancy Reports
```

Additional architecture documentation is available in `docs/architecture.md`.

---

# Project Structure

```text
medlens/

├── backend/
├── frontend/
├── docs/
│   ├── PRD.md
│   ├── architecture.md
│   ├── ai.md
│   ├── evaluation.md
│   ├── data-model.md
│   ├── roadmap.md
│   ├── api.md
│   ├── deployment.md
│   ├── design-decisions.md
│   └── testing.md
├── infra/
├── .github/
└── README.md
```

---

# Documentation

Project documentation is located in the `docs/` directory.

- Product Requirements Document
- Software Architecture
- AI Pipeline
- Model Evaluation
- Data Model
- Roadmap
- API Specification
- Testing Strategy
- Deployment Plan
- Design Decisions

---

# Roadmap

## Sprint 1 — Backend Foundation (Completed)

Completed:

- FastAPI backend
- PostgreSQL integration
- SQLAlchemy ORM
- Alembic migrations
- Docker development environment
- JWT authentication
- Health endpoint
- Initial backend test suite

---

## Sprint 2 — Core Application (In Progress)

Completed:

- Clinical document CRUD
- Paste document submission
- Text file upload
- PDF upload and text extraction

In Progress:

- React frontend
- Dashboard
- Medication data model
- Medication management

---

## Sprint 3 — AI Reconciliation

- Medication extraction
- Medication normalization
- Structured JSON validation
- Prompt engineering
- Reconciliation engine
- Documentation discrepancy detection
- Evidence-backed AI explanations

---

## Sprint 4 — Production Engineering

- AWS deployment
- CI/CD
- Automated testing
- Monitoring
- Performance optimization
- Production documentation

---

## Sprint 5 — Model Evaluation

- Integrate OpenBioLLM
- Integrate MedGemma
- Benchmark multiple LLM providers
- Compare extraction accuracy
- Measure JSON schema adherence
- Measure hallucination rates
- Compare latency
- Compare inference cost
- Document model selection

---

# Local Development

Clone the repository:

```bash
git clone https://github.com/built-by-ann/medlens.git
cd medlens
```

Start the development environment:

```bash
cd infra
docker compose up --build
```

Run the backend tests:

```bash
cd backend
source .venv/bin/activate
python -m pytest -v
```

Additional setup instructions will be added as development progresses.

---

# Project Status

### Completed

- Product requirements
- Software architecture
- Database design
- FastAPI backend
- PostgreSQL integration
- Docker development environment
- SQLAlchemy ORM
- Alembic migrations
- JWT authentication
- Health monitoring endpoint
- Backend API
- Clinical document CRUD
- Paste document submission
- Text file upload
- PDF upload and text extraction
- Backend test suite (40+ automated tests)

### In Progress

- Medication management
- React frontend
- AI extraction pipeline

### Planned

- Medication reconciliation engine
- Multi-model LLM evaluation
- Cloud deployment
- CI/CD
- Production monitoring

---

# Future Enhancements

Potential future improvements include:

- FHIR import/export
- RxNorm integration
- Timeline view of medication changes
- Background job processing
- Resolution workflow for discrepancies
- PDF reports
- CSV export
- Search across analyses
- Multi-model benchmarking dashboard
- Prompt versioning
- AI evaluation reports
- Cloud monitoring
- Kubernetes deployment
- Observability dashboard

---

# Disclaimer

MedLens is an educational software engineering project.

The application:

- Uses synthetic clinical data only
- Is not HIPAA compliant
- Does not provide medical advice
- Does not make clinical decisions
- Presents AI-generated findings for human review
- Is not intended for clinical use

---

# License

This project is licensed under the MIT License.
