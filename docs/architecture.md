# Architecture

## Overview

MedLens follows a modern three-tier web architecture consisting of a React frontend, FastAPI backend, PostgreSQL database, and external AI service integration. The frontend provides the user interface, the backend contains the application's business logic, PostgreSQL stores application data, and an AI service generates structured clinical insights from mock clinical notes.

---

## Goals

The architecture is designed to be:

- Modular
- Scalable
- Easy to test
- Easy to maintain
- Production-ready
- Easy to deploy with Docker

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

- Gemini API (or OpenAI)

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
             REST API
                  │
                  ▼
            FastAPI Backend
      ┌──────────┼──────────┐
      ▼          ▼          ▼
 PostgreSQL    AI API      AWS S3
```

---

## Core Components

### Frontend

Responsible for:

- Authentication
- Dashboard
- Clinical note upload
- Medication management
- Displaying analysis results

---

### Backend

Responsible for:

- Authentication
- API endpoints
- Business logic
- AI orchestration
- Medication reconciliation
- Database communication

---

### Database

Stores:

- Users
- Clinical Notes
- Medications
- Analyses
- Medication Flags

---

### AI Service

Responsible for:

- Clinical note summarization
- Medication extraction
- Condition extraction
- Follow-up recommendations

---

## Expected Data Flow

The expected application workflow is:

1. User logs in.
2. User uploads or pastes a mock clinical note.
3. Backend validates the request.
4. Backend stores the note.
5. Backend sends note text to the AI service.
6. AI returns structured JSON.
7. Backend validates the response.
8. Medication reconciliation logic compares extracted medications against the user's medication list.
9. Results are stored in PostgreSQL.
10. The frontend displays the completed analysis.

---

## Planned Database Relationships

```text
User
 ├── Clinical Notes
 ├── Medications
 └── Analyses

Analysis
 └── Medication Flags
```

---

## Security Considerations

The application will include:

- JWT authentication
- Password hashing
- Protected API routes
- Environment variables for secrets
- Input validation
- Structured AI output validation

Only synthetic clinical data will be used.

---

## Future Improvements

Potential future additions include:

- Background processing with Celery or FastAPI Background Tasks
- Redis
- AWS S3 integration
- CloudWatch logging
- Kubernetes deployment
- Sentry monitoring

---

## Notes

This document represents the intended architecture before implementation. It will evolve as the project is developed and design decisions are refined.