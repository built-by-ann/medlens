# Product Requirements Document (PRD)

# MedLens

**Version:** 1.0

**Status:** Planning

**Author:** Ann Mathew

---

# Overview

MedLens is an AI-powered healthcare workflow platform that helps users better understand mock clinical notes and medication lists by generating structured summaries and identifying potential medication documentation inconsistencies.

The project is inspired by research conducted at Vanderbilt University Medical Center on medication documentation inconsistencies within electronic health records. While MedLens is not intended for clinical use, it demonstrates how AI can organize healthcare information and support medication reconciliation workflows using synthetic data.

---

# Problem Statement

Clinical documentation can be difficult for patients and caregivers to interpret. Medication lists often become outdated or inconsistent across multiple clinical encounters, making it challenging to understand which medications are currently active.

This project explores how AI can assist in organizing clinical information, extracting structured data, and highlighting potential inconsistencies between documentation and medication lists.

---

# Goals

The project aims to:

- Build a production-quality full-stack web application
- Demonstrate modern software engineering practices
- Generate structured AI summaries from mock clinical notes
- Compare medication lists against note content
- Flag potential medication inconsistencies
- Store previous analyses for future review

---

# Non-Goals

The project is **not** intended to:

- Replace healthcare professionals
- Provide medical advice
- Diagnose patients
- Recommend treatments
- Process real patient information
- Function as an electronic health record (EHR)

---

# Target Users

### Primary Users

- Patients learning about healthcare information
- Caregivers organizing medication records
- Students exploring healthcare AI concepts
- Recruiters and employers evaluating the project

---

# MVP Features

The first version of MedLens will include:

## Authentication

- User registration
- User login
- JWT authentication
- Protected dashboard

---

## Clinical Notes

Users can:

- Paste clinical notes
- Upload `.txt` files
- Upload PDF files
- Save notes

---

## Medication Management

Users can:

- Add medications manually
- Update medications
- Delete medications
- Upload medication CSV files

---

## AI Analysis

Generate:

- Plain-language summary
- Conditions mentioned
- Medications mentioned
- Follow-up actions
- Medication inconsistency flags

---

## Dashboard

Users can:

- View previous analyses
- Review AI summaries
- Review medication flags
- Delete saved analyses

---

# User Stories

### Authentication

As a user, I want to create an account so that my analyses are saved securely.

As a user, I want to log in so I can access my previous analyses.

---

### Clinical Notes

As a user, I want to upload or paste a clinical note so that it can be analyzed by AI.

---

### Medication Management

As a user, I want to maintain an accurate medication list for comparison against uploaded notes.

---

### AI Analysis

As a user, I want the application to summarize clinical notes in plain language.

As a user, I want medications extracted automatically.

As a user, I want potential medication inconsistencies highlighted.

---

### Dashboard

As a user, I want to review previous analyses without uploading documents again.

---

# Functional Requirements

The system shall:

- Authenticate users
- Store user accounts securely
- Store uploaded clinical notes
- Manage medication lists
- Generate AI summaries
- Extract medications from notes
- Compare medications against user records
- Store completed analyses
- Display previous analyses

---

# Non-Functional Requirements

The application should be:

- Reliable
- Modular
- Secure
- Testable
- Maintainable
- Responsive
- Containerized
- Cloud deployable

---

# Success Criteria

The MVP will be considered successful if a user can:

1. Create an account.
2. Log in.
3. Upload or paste a mock clinical note.
4. Create a medication list.
5. Generate an AI analysis.
6. View medication inconsistency flags.
7. Return later to review saved analyses.

---

# Technical Stack

## Frontend

- React
- TypeScript
- Vite

## Backend

- FastAPI
- Python
- SQLAlchemy
- Alembic

## Database

- PostgreSQL

## AI

- Gemini API

## Infrastructure

- Docker
- Docker Compose
- GitHub Actions
- AWS EC2
- AWS S3 (future)

---

# Risks

Potential project risks include:

- AI hallucinations
- Incorrect medication extraction
- Unexpected API changes
- Cloud deployment issues
- Authentication bugs

Mitigation strategies include:

- Structured JSON responses
- Pydantic validation
- Automated testing
- Manual review during development

---

# Future Enhancements

Potential future improvements include:

- Background job processing
- Search across analyses
- PDF export
- JSON export
- CSV export
- AI explanation improvements
- Observability dashboard
- Cloud monitoring
- Kubernetes deployment

---

# Ethical Considerations

MedLens is an educational software engineering project.

The application:

- Uses synthetic clinical data only
- Is not HIPAA compliant
- Does not provide medical advice
- Should not be used for clinical decision-making
- Is intended to demonstrate AI-assisted software engineering concepts

---

# Definition of Success

By completion, MedLens should demonstrate:

- Production-style software architecture
- Full-stack web development
- AI integration
- Authentication
- Database design
- Docker containerization
- Cloud deployment
- Automated testing
- CI/CD
- Technical documentation
- Agile project management

The completed application should serve as a portfolio project showcasing modern software engineering practices and AI integration in a healthcare-inspired domain.