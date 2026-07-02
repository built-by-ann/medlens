# Product Requirements Document (PRD)

# MedLens

**Version:** 2.0

**Status:** Planning

**Author:** Ann Mathew

---

# Overview

MedLens is an AI-powered clinical documentation reconciliation platform that compares medication information across multiple clinical documents, identifies potential documentation inconsistencies, and presents evidence-backed findings for human review.

Inspired by research conducted at Vanderbilt University Medical Center on medication documentation inconsistencies within electronic health records, MedLens demonstrates how AI can assist with medication reconciliation workflows by extracting structured medication information from synthetic clinical documents and identifying discrepancies across documentation sources.

MedLens is an educational software engineering project and is not intended for clinical use or medical decision-making.

---

# Problem Statement

Medication information is often documented in multiple locations throughout a patient's healthcare record, including medication lists, visit notes, discharge summaries, progress notes, and medication reconciliation documents.

Over time these documentation sources can become inconsistent. A medication may be documented as active in one location, discontinued in another, or omitted entirely from a separate document. Identifying these inconsistencies requires manual review across multiple sources and can be both time-consuming and error-prone.

MedLens explores how AI can extract structured medication information from multiple clinical documents, compare documentation sources, and highlight potential medication reconciliation issues for human review.

---

# Goals

The project aims to:

- Build a production-quality full-stack web application
- Demonstrate modern software engineering practices
- Extract structured medication information from clinical documents
- Compare medication information across documentation sources
- Identify potential medication reconciliation issues
- Generate evidence-backed discrepancy reports
- Store previous analyses for future review
- Showcase AI integration within a realistic healthcare workflow

---

# Non-Goals

The project is **not** intended to:

- Replace healthcare professionals
- Provide medical advice
- Diagnose patients
- Recommend treatments
- Modify clinical documentation automatically
- Process real patient information
- Function as an electronic health record (EHR)

---

# Target Users

## Primary Users

- Healthcare software engineering students
- Researchers working with synthetic clinical data
- Developers exploring AI-assisted healthcare workflows

## Secondary Users

- Recruiters evaluating software engineering projects
- Employers assessing full-stack engineering skills
- Educators demonstrating AI-assisted clinical documentation concepts

---

# MVP Features

## Authentication

Users can:

- Register for an account
- Log in securely
- Maintain authenticated sessions
- Access a protected dashboard

---

## Clinical Documents

Users can:

- Upload medication lists
- Upload visit notes
- Upload discharge summaries
- Upload progress notes
- Paste document text
- Upload PDF files
- Upload text files
- View previously uploaded documents

---

## AI Medication Extraction

The application will:

- Extract medication mentions
- Extract dosage information
- Extract medication frequency
- Extract medication route
- Infer medication status
- Normalize medication names
- Preserve supporting context from the source document

---

## Reconciliation Analysis

Users can:

- Select multiple clinical documents
- Run an AI reconciliation analysis
- Compare medication information across documentation sources
- View detected discrepancies
- Review AI-generated explanations
- Review supporting evidence
- Save completed analyses

---

## Dashboard

Users can:

- View previous analyses
- View uploaded clinical documents
- Review discrepancy reports
- Review AI summaries
- Search previous analyses
- Delete saved analyses

---

# User Stories

## Authentication

As a user, I want to create an account so that my analyses are saved securely.

As a user, I want to log in so I can access my previous analyses.

---

## Clinical Documents

As a user, I want to upload multiple clinical documents so they can be compared.

As a user, I want to paste document text directly when I do not have a file.

---

## AI Medication Extraction

As a user, I want medications automatically extracted from each document.

As a user, I want extracted medications normalized into a consistent format.

---

## Reconciliation Analysis

As a user, I want medication information compared across documentation sources.

As a user, I want potential medication discrepancies highlighted automatically.

As a user, I want each discrepancy explained using evidence from the uploaded documents.

---

## Dashboard

As a user, I want to review previous analyses without uploading documents again.

---

# Functional Requirements

The system shall:

- Authenticate users
- Store user accounts securely
- Store uploaded clinical documents
- Extract medication information from uploaded documents
- Normalize medication terminology
- Compare medication information across multiple documentation sources
- Generate reconciliation analyses
- Store discrepancy reports
- Display supporting evidence for every discrepancy
- Store completed analyses
- Display previous analyses

---

# Non-Functional Requirements

The application should be:

- Reliable
- Secure
- Modular
- Maintainable
- Testable
- Responsive
- Containerized
- Cloud deployable
- Well documented

---

# Success Criteria

The MVP will be considered successful if a user can:

1. Create an account.
2. Log in.
3. Upload multiple synthetic clinical documents.
4. Generate a reconciliation analysis.
5. Review extracted medications.
6. Review documentation discrepancies with supporting evidence.
7. Save the completed analysis.
8. Return later to review previous analyses.

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

- Google Gemini API

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
- Medication normalization errors
- False-positive discrepancy detection
- API changes
- Authentication bugs
- Cloud deployment issues

Mitigation strategies include:

- Structured JSON outputs
- Pydantic validation
- Confidence scoring
- Human review of every discrepancy
- Automated testing
- Comprehensive logging

---

# Future Enhancements

Potential future improvements include:

- Background job processing
- Resolution workflow for discrepancies
- Timeline view of medication changes
- FHIR import
- FHIR export
- RxNorm integration
- Search across analyses
- PDF export
- CSV export
- JSON export
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
- Does not make clinical decisions
- Does not modify patient records
- Should not be used for clinical decision-making
- Presents AI-generated findings for human review only

---

# Definition of Success

By completion, MedLens should demonstrate:

- Production-style software architecture
- Full-stack web development
- AI-assisted information extraction
- Clinical documentation reconciliation workflows
- Authentication and authorization
- Relational database design
- Docker containerization
- Cloud deployment
- Automated testing
- CI/CD pipelines
- Comprehensive technical documentation
- Agile software development practices

The completed application should serve as a flagship portfolio project demonstrating modern software engineering, AI integration, backend architecture, cloud deployment, and thoughtful product design around a realistic healthcare documentation workflow.