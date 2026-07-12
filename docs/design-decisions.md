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

# Decision 10: Database-Level ON DELETE SET NULL for Reconciliation Findings

**Decision**

Use `ON DELETE SET NULL` on the foreign keys from MedicationDiscrepancy to Medication and to MedicationMention, enforced at the database level.

**Reasoning**

Every other foreign key in the schema relies only on ORM-level cascade behavior, not a database-level `ON DELETE` action. MedicationDiscrepancy is a deliberate exception, because a reconciliation finding is a record of something that was true at analysis time. If the referenced Medication or MedicationMention is later deleted, the finding should survive with the reference cleared rather than being deleted along with it, and the referenced Medication or MedicationMention should never be deleted as a side effect of removing a finding.

**Trade-offs**

Pros

- Findings are not silently lost when a medication or mention is later removed
- A user's medication records and clinical evidence cannot be deleted as a side effect of finding cleanup
- Enforced at the database level, not only through application code

Cons

- Introduces a schema convention that differs from every other foreign key in the project
- Requires readers of the schema to understand why this table is treated differently

---

# Decision 11: Association Table for Analysis and ClinicalDocument

**Decision**

Represent the relationship between Analysis and ClinicalDocument with a dedicated association table, analysis_clinical_documents, using a composite primary key and `ON DELETE CASCADE` on both foreign keys, rather than a foreign key on either model.

**Reasoning**

An analysis can cover more than one clinical document, and the same document can be included in more than one analysis. A foreign key on Analysis or on ClinicalDocument can only represent a single direction of that relationship, so a true many to many association requires its own table. Unlike MedicationDiscrepancy's references, an association row carries no meaning of its own beyond linking one analysis to one document, so there is nothing to preserve if either side is deleted. `ON DELETE CASCADE` removes the link automatically, while leaving the analysis, its other documents, and its findings intact, and leaving the document and its other analyses intact.

The table uses a composite primary key of analysis_id and clinical_document_id instead of a surrogate id column, which is a deliberate exception to this project's usual pattern of giving every table a surrogate id. The composite key already uniquely identifies each link, and the table has no other attributes that would need a single id to reference.

**Trade-offs**

Pros

- Correctly represents a many to many relationship without duplicating document content or creating a second document table
- Link rows are cleaned up automatically, at the database level, when either side is deleted
- Composite primary key avoids an unused surrogate id on a table with no independent attributes

Cons

- First table in the project without a surrogate id column, which differs from the rest of the schema
- Adds a table whose sole purpose is linking, which the reconciliation service must join through when loading an analysis's documents

---

# Future Decisions

Additional architectural decisions will be documented as the project evolves, including topics such as:

- Background job processing
- Caching
- AWS architecture
- Deployment strategy
- Monitoring
- Performance optimization