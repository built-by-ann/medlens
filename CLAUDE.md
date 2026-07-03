# CLAUDE.md

## Project Overview

MedLens is an AI-powered clinical documentation reconciliation platform.

The application allows users to upload multiple synthetic clinical documents, extract structured medication information using AI, compare medication information across documentation sources, and identify potential medication documentation inconsistencies for human review.

This project is inspired by research conducted at Vanderbilt University Medical Center on medication documentation inconsistencies within electronic health records.

MedLens is an educational software engineering project. It uses synthetic clinical data only and is not intended for clinical use.

---

# Product Philosophy

MedLens is **not** an AI chatbot.

The value of the application comes from the workflow surrounding AI rather than the language model itself.

The workflow is:

Clinical Documents

↓

AI Medication Extraction

↓

Medication Normalization

↓

Reconciliation Engine

↓

Medication Discrepancy Report

↓

Dashboard

The AI is only one component of the overall system.

---

# Core Responsibilities

## The Application

The application is responsible for:

- User authentication
- Clinical document management
- Database persistence
- Medication reconciliation
- Business logic
- Dashboard
- Analysis history
- Discrepancy reporting

## The AI

The AI is responsible for:

- Extracting medications
- Extracting dosage
- Extracting frequency
- Extracting route
- Inferring medication status
- Generating structured JSON
- Explaining identified discrepancies

The AI should never make clinical decisions.

---

# Current Data Model

```text
User
 │
 ├── ClinicalDocument
 │      └── MedicationMention
 │
 └── Analysis
        └── MedicationDiscrepancy
```

Relationships

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

# Tech Stack

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

## Database

- PostgreSQL

## Infrastructure

- Docker
- Docker Compose
- GitHub Actions
- AWS EC2
- AWS S3 (planned)

---

# Architecture Principles

- Keep the frontend focused on presentation.
- Keep business logic in the backend.
- Keep AI provider logic isolated from application logic.
- Prefer deterministic backend logic whenever possible.
- Validate every AI response using Pydantic.
- Store structured data rather than raw AI output.
- Design the AI layer so providers can be swapped without changing business logic.
- Keep components modular and loosely coupled.

---

# Coding Guidelines

## General

- Prefer readability over cleverness.
- Write production-quality code.
- Keep functions small and focused.
- Avoid unnecessary abstractions.
- Keep changes scoped to the active GitHub issue.
- Do not modify unrelated files.

---

## FastAPI

- Keep route handlers thin.
- Move business logic into service modules.
- Use dependency injection where appropriate.
- Return Pydantic response models.
- Use proper HTTP status codes.

---

## SQLAlchemy

- One model per file.
- Define relationships explicitly.
- Use Alembic for schema changes.
- Never modify the database schema manually.
- Prefer ORM operations over raw SQL.

---

## React

- Use functional components.
- Keep components small.
- Reuse UI components where possible.
- Keep business logic outside presentation components.

---

## AI Integration

- Never hardcode prompts throughout the codebase.
- Centralize prompt definitions.
- Always request structured JSON output.
- Validate every response before storing it.
- Handle malformed responses gracefully.

---

# Git Workflow

- One GitHub Issue per feature.
- One feature branch per issue.
- One pull request per issue.
- Keep commits focused.
- Do not create commits automatically.
- Do not push automatically.
- Never merge branches automatically.

---

# Documentation

Whenever functionality changes significantly:

- Update README.md
- Update documentation in docs/
- Keep architecture documentation current.
- Document major design decisions.

---

# Dependencies

Before introducing a new dependency:

- Explain why it is needed.
- Prefer existing project dependencies.
- Avoid unnecessary packages.

---

# Testing

Whenever possible:

- Add or update tests.
- Do not remove existing tests.
- Explain how to manually verify changes.

---

# Security

- Never hardcode secrets.
- Never commit API keys.
- Use environment variables.
- Validate all user input.
- Assume uploaded files may be malformed.
- Use synthetic clinical data only.

---

# Before Making Changes

Before writing code:

1. Read the relevant GitHub issue.
2. Review existing project structure.
3. Explain the implementation plan.
4. Identify affected files.
5. Wait for approval before making major architectural changes.

---

# After Making Changes

Always provide:

1. Summary of changes
2. Files modified
3. Testing instructions
4. Any follow-up recommendations

---

# What Not To Do

Do not:

- Change project architecture without discussion.
- Introduce unrelated refactors.
- Add unnecessary dependencies.
- Hardcode credentials.
- Use real patient data.
- Implement medical decision-making.
- Make commits or push changes automatically.
- Modify multiple GitHub issues in a single change.

---

# Development Commands

## Backend

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

## Database

```bash
alembic current
alembic revision --autogenerate -m "<message>"
alembic upgrade head
```

## Docker

```bash
cd infra
docker compose up --build
```

---

# Current Project Status

Completed

- Project structure
- Product requirements
- README
- Architecture documentation
- Data model
- FastAPI setup
- Docker
- PostgreSQL
- SQLAlchemy
- Alembic
- Initial database models

Current Focus

- Authentication
- Backend API development

Upcoming

- Clinical document uploads
- AI medication extraction
- Reconciliation engine
- React frontend
- Cloud deployment

---

# Goal

The goal of this project is not simply to integrate an LLM.

The goal is to build a production-quality software system that demonstrates modern full-stack engineering practices while solving a realistic clinical documentation reconciliation problem through thoughtful integration of AI.