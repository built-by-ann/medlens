# MedLens

An AI-powered healthcare platform that analyzes mock clinical notes and medication lists to generate structured summaries, identify potential medication documentation inconsistencies, and demonstrate production-grade software engineering practices.

> **Status:** In Development

---

## Overview

MedLens is a full-stack AI healthcare application inspired by research on medication documentation inconsistencies conducted at Vanderbilt University Medical Center.

The application allows users to upload or paste mock clinical notes, manage medication lists, and receive AI-generated summaries along with potential medication reconciliation issues. While not intended for clinical use, MedLens demonstrates how modern AI systems can assist in organizing healthcare information through a secure, production-style architecture.

The project is designed to showcase full-stack software engineering, cloud deployment, testing, containerization, and AI integration.

---

## Motivation

Medication documentation inconsistencies are a common challenge in healthcare systems. Clinical notes, medication lists, and patient records can become misaligned over time, making it difficult to understand which medications are currently active.

This project explores how AI can assist with:

- Organizing clinical documentation
- Summarizing visit notes
- Extracting medication information
- Identifying potential documentation inconsistencies
- Presenting healthcare information in a structured, user-friendly format

The application uses **synthetic data only** and is intended solely for educational and portfolio purposes.

---

## Planned Features

### Authentication

- User registration
- User login
- JWT authentication
- Protected dashboard

### Clinical Notes

- Paste clinical notes
- Upload `.txt` files
- Upload PDF files
- Save previous notes

### Medication Management

- Manual medication entry
- Medication CRUD
- CSV medication upload

### AI Analysis

- Plain-language summaries
- Medication extraction
- Condition extraction
- Follow-up recommendations
- Medication inconsistency detection

### Dashboard

- Saved analyses
- Analysis history
- Medication flags
- Delete analyses

---

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

- Gemini API

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

---

## Architecture

```
                User
                  │
                  ▼
      React + TypeScript Frontend
                  │
             REST API
                  │
                  ▼
            FastAPI Backend
      ┌──────────┼──────────┐
      ▼          ▼          ▼
 PostgreSQL    AI API      AWS S3
```

Additional architecture documentation is available in `docs/architecture.md`.

---

## Project Structure

```
medlens/

├── backend/
├── frontend/
├── docs/
├── infra/
├── .github/
└── README.md
```

---

## Documentation

Project documentation can be found in the `docs/` directory.

- Product Requirements Document
- Architecture
- Roadmap
- API Specification
- Testing Strategy
- Deployment Plan
- Design Decisions

---

## Roadmap

### Sprint 1

- Project setup
- Authentication
- PostgreSQL
- Docker
- FastAPI foundation

### Sprint 2

- Clinical note uploads
- Medication management
- AI summaries
- Medication reconciliation

### Sprint 3

- React frontend
- Dashboard
- User experience
- Responsive design

### Sprint 4

- AWS deployment
- CI/CD
- Testing
- Documentation
- Production engineering

---

## Local Development

Setup instructions will be added as development progresses.

The project will be containerized using Docker Compose for reproducible local development.

---

## Project Status

Current phase:

- Product planning completed
- Architecture design completed
- Technical documentation completed
- Backend development in progress

---

## Future Improvements

Potential future enhancements include:

- Background job processing
- Search functionality
- PDF exports
- Cloud monitoring
- Kubernetes deployment
- Observability dashboard

---

## Disclaimer

MedLens is an educational software engineering project.

- Uses synthetic healthcare data only
- Not HIPAA compliant
- Does not provide medical advice
- Not intended for clinical decision-making

---

## License

This project is licensed under the MIT License.