# MedLens

An AI-powered clinical documentation reconciliation platform that extracts medication information from multiple clinical documents, identifies potential medication documentation inconsistencies, and demonstrates production-grade software engineering practices.

**Status:** Active Development

## Overview

MedLens is a full-stack AI application inspired by research conducted at Vanderbilt University Medical Center on medication documentation inconsistencies within electronic health records.

The application allows users to upload multiple synthetic clinical documents—including medication lists, visit notes, discharge summaries, progress notes, and medication reconciliation forms. AI extracts structured medication information from each document, compares information across documentation sources, and highlights potential medication reconciliation issues with evidence supporting each finding.

Rather than functioning as an AI chatbot, MedLens demonstrates how large language models can be integrated into a realistic clinical documentation workflow through a production-style software architecture.

The project is built to showcase modern software engineering practices, including full-stack development, cloud deployment, containerization, automated testing, CI/CD, and AI integration.

## Motivation

Medication information often exists in multiple locations throughout a patient's healthcare record. A medication may appear in a medication list, visit note, discharge summary, or medication reconciliation document, and these sources do not always remain consistent over time.

During research at Vanderbilt University Medical Center, I studied medication documentation inconsistencies within electronic health records. MedLens was inspired by that work and explores how AI can assist by extracting medication information from multiple clinical documents, comparing documentation sources, and surfacing potential reconciliation issues for human review.

The application uses **synthetic clinical data only** and is intended solely for educational and portfolio purposes.

## How It Works

1. Upload one or more synthetic clinical documents.
2. AI extracts structured medication information from each document.
3. Medication names and statuses are normalized into a consistent format.
4. MedLens compares medication information across documentation sources.
5. Potential medication documentation inconsistencies are identified.
6. Evidence-backed discrepancy reports are generated for human review.
7. Completed analyses are saved for future reference.

## Planned Features

### Authentication

- User registration
- User login
- JWT authentication
- Protected dashboard

### Clinical Documents

Users can:

- Upload medication lists
- Upload visit notes
- Upload discharge summaries
- Upload progress notes
- Upload PDF files
- Upload text files
- Paste document text
- View previously uploaded documents

### AI Medication Extraction

The application will:

- Extract medication names
- Extract dosage information
- Extract medication frequency
- Extract medication route
- Infer medication status
- Normalize medication terminology
- Preserve supporting context from the source document

### Reconciliation Analysis

Users can:

- Compare medication information across multiple documentation sources
- Detect medication documentation inconsistencies
- View evidence supporting each discrepancy
- Review AI-generated explanations
- Save completed reconciliation analyses

### Dashboard

Users can:

- View uploaded clinical documents
- Review previous analyses
- Search saved analyses
- Review discrepancy reports
- Delete saved analyses

## Technology Stack

### Frontend

- React
- TypeScript
- Vite
- React Router

### Backend

- FastAPI
- Python
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
- AWS S3 (planned)

### Testing

- pytest
- Vitest
- React Testing Library
- Playwright (planned)

## Architecture

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
      ┌───────────────┼────────────────┐
      ▼               ▼                ▼
PostgreSQL      Gemini API      Reconciliation Engine
      │               │                │
      └───────────────┴────────────────┘
                      │
                      ▼
         Medication Discrepancy Reports
```

Additional architecture documentation is available in `docs/architecture.md`.

## Project Structure

```text
medlens/

├── backend/
├── frontend/
├── docs/
│   ├── PRD.md
│   ├── architecture.md
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

## Documentation

Project documentation is located in the `docs/` directory.

- Product Requirements Document
- Architecture
- Data Model
- Roadmap
- API Specification
- Testing Strategy
- Deployment Plan
- Design Decisions

## Roadmap

### Sprint 1 — Backend Foundation

- FastAPI backend
- PostgreSQL integration
- SQLAlchemy ORM
- Alembic migrations
- Authentication
- Docker development environment
- Initial database models

### Sprint 2 — Core Application

- React frontend
- Clinical document uploads
- Dashboard
- Document management
- Responsive user interface

### Sprint 3 — AI Reconciliation

- Medication extraction
- Medication normalization
- Reconciliation engine
- Documentation discrepancy detection
- Evidence-backed AI explanations

### Sprint 4 — Production Engineering

- AWS deployment
- CI/CD
- Automated testing
- Monitoring
- Performance optimization
- Production documentation

## Local Development

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

Additional setup instructions will be added as development progresses.

## Project Status

Completed:

- Product requirements
- Software architecture
- Database design
- FastAPI backend
- PostgreSQL integration
- Docker development environment
- SQLAlchemy configuration
- Alembic migrations
- Initial database models

In Progress:

- Authentication
- Backend API development

Planned:

- React frontend
- AI reconciliation engine
- Cloud deployment
- Automated testing

## Future Enhancements

Potential future improvements include:

- FHIR import/export
- RxNorm integration
- Timeline view of medication changes
- Background job processing
- Resolution workflow for discrepancies
- PDF reports
- CSV export
- Search across analyses
- Cloud monitoring
- Kubernetes deployment
- Observability dashboard

## Disclaimer

MedLens is an educational software engineering project.

The application:

- Uses synthetic clinical data only
- Is not HIPAA compliant
- Does not provide medical advice
- Does not make clinical decisions
- Presents AI-generated findings for human review
- Is not intended for clinical use

## License

This project is licensed under the MIT License.