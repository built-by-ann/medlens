# Roadmap

## Overview

This roadmap outlines the planned development phases for MedLens. The project is organized into four sprints: foundation, core AI analysis, frontend user experience, and production engineering.

---

## Sprint 1: Foundation

**Goal:** Set up the project structure, backend foundation, database, Docker environment, and authentication.

### Planned Work

- Initialize monorepo structure
- Write starter documentation
- Set up FastAPI backend
- Set up React + TypeScript frontend
- Configure Docker Compose
- Connect PostgreSQL
- Add SQLAlchemy
- Add Alembic migrations
- Design initial database models
- Implement user registration
- Implement user login
- Add JWT authentication
- Add protected user endpoint
- Add `/health` endpoint
- Add initial backend tests

### Deliverable

A Dockerized backend with authentication, database connectivity, health checks, and initial test coverage.

---

## Sprint 2: Core AI Analysis

**Goal:** Build the main healthcare analysis functionality.

### Planned Work

- Add clinical note model and endpoints
- Support pasted clinical notes
- Support `.txt` file uploads
- Add PDF text extraction
- Add medication CRUD endpoints
- Add medication CSV upload
- Build medication reconciliation service
- Add medication flag model
- Add analysis model
- Integrate AI summary service
- Require structured JSON AI responses
- Validate AI responses with Pydantic
- Store analysis results
- Add analysis detail and delete endpoints
- Add reconciliation unit tests
- Add full analysis integration test

### Deliverable

A backend workflow where a user can submit a mock clinical note and medication list, then receive a saved AI-generated summary and medication inconsistency flags.

---

## Sprint 3: Frontend & User Experience

**Goal:** Build a complete user-facing workflow.

### Planned Work

- Configure frontend routing
- Build signup page
- Build login page
- Add authentication state management
- Build protected dashboard
- Build clinical note upload page
- Build medication entry form
- Build medication CSV upload UI
- Build analysis loading state
- Build analysis results page
- Display medication inconsistency flags
- Display AI summary and follow-up actions
- Add delete analysis UI
- Add responsive styling
- Add frontend error handling
- Add frontend component tests

### Deliverable

A complete user flow from account creation to clinical note analysis and saved results.

---

## Sprint 4: Production Engineering

**Goal:** Make the project portfolio-ready with deployment, testing, documentation, and production-style engineering practices.

### Planned Work

- Add backend linting and formatting
- Add frontend linting and TypeScript checks
- Create backend GitHub Actions workflow
- Create frontend GitHub Actions workflow
- Validate Docker image builds
- Deploy application to AWS EC2
- Integrate AWS S3 file storage
- Add structured logging
- Add request timing metrics
- Improve `/health` endpoint
- Write API documentation
- Write testing documentation
- Write deployment documentation
- Write architecture documentation
- Write design decisions document
- Add screenshots to README
- Record demo video
- Create version 1.0 release
- Polish README
- Write resume-ready project bullets

### Deliverable

A deployed, documented, tested, Dockerized AI healthcare platform with CI/CD, production-style logging, and a polished portfolio presentation.

---

## MVP Scope

The MVP includes:

- User authentication
- Clinical note upload or paste input
- Medication list entry
- AI-generated structured summary
- Medication inconsistency flags
- Saved analysis results
- Dashboard
- Basic tests
- Dockerized local development

---

## Out of Scope for MVP

The first version will not include:

- Real patient data
- HIPAA compliance
- Medical advice
- Clinician decision support
- Insurance workflows
- Hospital administration tools
- Wearable integrations
- Full EHR functionality

---

## Long-Term Improvements

Potential future improvements include:

- Background processing with Redis and Celery
- AWS RDS
- CloudWatch logging
- Sentry monitoring
- Search across previous analyses
- PDF export
- JSON and CSV exports
- Admin observability dashboard
- Custom domain
- Kubernetes deployment

---

## Project North Star

By the end of the project, MedLens should demonstrate the ability to build, test, document, containerize, and deploy a full-stack AI healthcare application using modern software engineering practices.