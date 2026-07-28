# MedLens

An AI-powered clinical documentation reconciliation platform that
extracts medication information from multiple clinical documents,
identifies potential documentation inconsistencies, and demonstrates
production-grade software engineering practices.

**Status:** Active Development (Sprint 3)

------------------------------------------------------------------------

# Overview

MedLens is a full-stack AI application inspired by research conducted at
Vanderbilt University Medical Center on medication documentation
inconsistencies within electronic health records.

Users securely authenticate, upload synthetic clinical documents by
pasting text or uploading TXT and PDF files, and generate AI-powered
medication reconciliation analyses.

The application extracts structured medication information from multiple
clinical documents (including medication lists, visit notes, discharge
summaries, progress notes, and medication reconciliation forms) and
compares information across documentation sources to identify potential
documentation inconsistencies with evidence supporting each finding.

Rather than functioning as an AI chatbot, MedLens demonstrates how large
language models can be integrated into a realistic clinical
documentation workflow through a production-style software architecture.

The project showcases modern software engineering practices including:

- Full-stack web development
- REST API design
- Provider-agnostic AI integration
- Containerization with Docker
- PostgreSQL database design
- Automated testing
- CI/CD-ready architecture
- Cloud deployment planning

------------------------------------------------------------------------

# Motivation

Medication information often exists in multiple locations throughout a
patient's healthcare record. During research at Vanderbilt University
Medical Center, I studied medication documentation inconsistencies
within electronic health records. MedLens was inspired by that work and
explores how AI can assist by extracting medication information from
multiple clinical documents, comparing documentation sources, and
surfacing potential reconciliation issues for human review.

**MedLens uses synthetic clinical data only and is intended solely for
educational and portfolio purposes.**

------------------------------------------------------------------------

# How It Works

1. Register and authenticate using JWT.
2. Upload one or more synthetic clinical documents.
3. AI extracts structured medication information.
4. Medication information is normalized.
5. A deterministic reconciliation engine compares documentation
 sources.
6. Potential discrepancies are identified.
7. Evidence-backed reports are generated.
8. Completed analyses are saved, retrieved, and managed.

------------------------------------------------------------------------

# Current Features

## Authentication

Implemented

- User registration
- User login
- JWT authentication
- Protected API endpoints

## Clinical Documents

Implemented

- Paste document text
- Upload TXT files
- Upload PDF files
- View documents
- Delete documents

## Medication Management

Implemented

- Full medication CRUD
- User-owned medication lists
- CSV import support

## AI Analysis

Implemented

- Google Gemini integration
- Provider-agnostic AI architecture
- Prompt template system
- Structured JSON validation
- Medication extraction
- Analysis persistence
- Analysis retrieval
- Analysis deletion

Planned

- OpenBioLLM integration
- MedGemma integration
- Provider benchmarking

## Reconciliation

Implemented

- Deterministic reconciliation engine
- Medication discrepancy detection
- Evidence-backed findings
- AI-generated summaries

## Dashboard

In Development

- Authentication UI
- Document management
- Analysis history
- Analysis detail view
- Responsive dashboard

------------------------------------------------------------------------

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

- Google Gemini
- Provider abstraction layer

Planned: - OpenBioLLM - MedGemma

## Infrastructure

- Docker
- Docker Compose

Planned: - GitHub Actions - AWS EC2 - AWS S3

## Testing

- pytest
- Unit tests
- Service tests
- Route tests
- Integration tests
- Authentication tests
- Medication CRUD tests
- Clinical document CRUD tests
- Reconciliation engine tests
- Analysis workflow tests

Frontend planned: - Vitest - React Testing Library - Playwright

------------------------------------------------------------------------

# Documentation

Documentation is available in the `docs/` directory:

- Product Requirements
- Architecture
- Frontend Architecture
- AI Pipeline
- Evaluation Plan
- Data Model
- API Specification
- Testing Strategy
- Deployment Plan
- Design Decisions
- Roadmap

------------------------------------------------------------------------

# Roadmap

## Sprint 1 --- Backend Foundation 

- FastAPI backend
- PostgreSQL
- SQLAlchemy
- Alembic
- Docker
- JWT authentication
- Health endpoint
- Backend testing foundation

## Sprint 2 --- AI Analysis Backend 

- Clinical document CRUD
- Medication CRUD
- TXT/PDF upload
- AI provider architecture
- Gemini integration
- Prompt templates
- Medication extraction
- Reconciliation engine
- Analysis persistence
- Analysis retrieval
- Analysis deletion
- Comprehensive backend testing

## Sprint 3 --- Frontend Application 

- React frontend
- Authentication
- Dashboard
- Upload workflow
- Analysis history
- Analysis details
- Responsive UI
- Frontend testing

## Sprint 4 --- Production Engineering

- AWS deployment
- CI/CD
- Monitoring
- Performance optimization

## Sprint 5 --- Model Evaluation

- OpenBioLLM
- MedGemma
- Multi-model benchmarking
- Accuracy, latency, and cost evaluation

------------------------------------------------------------------------

# Local Development

Clone the repository:

``` bash
git clone https://github.com/built-by-ann/medlens.git
cd medlens
```

Start the backend:

``` bash
cd infra
docker compose up --build
```

Run the frontend:

``` bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Run backend tests:

``` bash
cd backend
source .venv/bin/activate
python -m pytest -v
```

------------------------------------------------------------------------

# Project Status

## Completed

- Backend architecture
- Authentication
- Clinical document management
- Medication management
- AI provider abstraction
- Gemini integration
- Medication extraction
- Reconciliation engine
- Analysis lifecycle
- Comprehensive backend test suite

## In Progress

- React frontend
- Dashboard
- User experience
- Frontend testing

## Planned

- Additional LLM providers
- Cloud deployment
- CI/CD
- Production monitoring

------------------------------------------------------------------------

# Future Enhancements

- FHIR integration
- RxNorm integration
- Timeline visualization
- Background jobs
- PDF reports
- CSV export
- Prompt versioning
- Multi-model evaluation dashboard

------------------------------------------------------------------------

# Disclaimer

MedLens is an educational software engineering project.

- Uses synthetic clinical data only
- Is not HIPAA compliant
- Does not provide medical advice
- Is not intended for clinical use

------------------------------------------------------------------------

# License

This project is licensed under the MIT License.
