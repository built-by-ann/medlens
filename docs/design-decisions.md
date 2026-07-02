# Design Decisions

## Overview

This document records significant architectural and technical decisions made during the development of MedLens. As the project evolves, new decisions and trade-offs will be documented here.

---

# Decision 1: FastAPI instead of Flask

**Decision**

Use FastAPI as the backend framework.

**Reasoning**

FastAPI provides automatic request validation, OpenAPI documentation, strong typing through Pydantic, and excellent performance. It is well-suited for modern REST APIs and AI applications.

**Trade-offs**

Pros

- Automatic API documentation
- Built-in request validation
- Excellent async support
- Strong type safety

Cons

- Smaller ecosystem than Flask
- Slight learning curve

---

# Decision 2: PostgreSQL instead of MongoDB

**Decision**

Use PostgreSQL as the primary database.

**Reasoning**

The application's data is highly relational. Users own notes, medications, analyses, and medication flags, making a relational database a natural fit.

**Trade-offs**

Pros

- Strong schema enforcement
- ACID compliance
- Excellent relational querying
- Mature ecosystem

Cons

- Less flexible than document databases
- Requires schema migrations

---

# Decision 3: React + TypeScript

**Decision**

Use React with TypeScript for the frontend.

**Reasoning**

TypeScript improves maintainability by catching errors at compile time and providing stronger editor support. React offers a component-based architecture suitable for scalable frontend development.

---

# Decision 4: Docker for Development

**Decision**

Containerize the application using Docker and Docker Compose.

**Reasoning**

Docker provides consistent development environments across machines and simplifies deployment.

Benefits include:

- Reproducible environments
- Easier onboarding
- Simplified deployment
- Isolated dependencies

---

# Decision 5: Structured AI Responses

**Decision**

Require the AI model to return structured JSON rather than free-form text.

**Reasoning**

Structured responses can be validated, tested, and safely integrated into downstream application logic.

Instead of:

- Long paragraphs

Return:

- Summary
- Conditions
- Medications
- Follow-up actions

This improves reliability and reduces parsing errors.

---

# Decision 6: Validate AI Output with Pydantic

**Decision**

Treat AI responses as untrusted input.

**Reasoning**

Large language models can return malformed or unexpected responses. Every AI response should be validated before being stored or displayed.

---

# Decision 7: Service-Oriented Backend

**Decision**

Separate API routes from business logic.

**Reasoning**

Routes should primarily handle HTTP requests and responses, while business logic belongs in dedicated service modules.

Example:

- Authentication Service
- AI Service
- Medication Service
- Analysis Service

Benefits:

- Easier testing
- Better organization
- Improved maintainability

---

# Decision 8: Synthetic Data Only

**Decision**

Use only synthetic clinical notes and medication lists.

**Reasoning**

The project is intended as a portfolio application and should not process real patient information.

Benefits:

- No HIPAA concerns
- Easier sharing and deployment
- Safe public demonstrations

---

# Decision 9: Agile Project Management

**Decision**

Manage development using GitHub Issues, Milestones, Project Boards, feature branches, and pull requests.

**Reasoning**

The goal is to simulate a professional software engineering workflow rather than simply producing working code.

---

# Future Decisions

Additional architectural decisions will be documented as the project evolves, including topics such as:

- Background job processing
- Caching
- AWS architecture
- Deployment strategy
- Monitoring
- Performance optimization