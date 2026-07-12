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

# Decision 12: Deterministic Reconciliation Without AI or Fuzzy Matching

**Decision**

Implement medication reconciliation as explicit, deterministic backend logic. Medication names and fields are compared using fixed normalization rules and a small, explicit alias list. No fuzzy matching library, vector search, or LLM call is used anywhere in the comparison itself.

**Reasoning**

AI is responsible for producing MedicationMention records from clinical text. Deciding whether two already-structured records conflict is a comparison problem, not an extraction problem, and does not need a language model. A deterministic implementation is reproducible, directly unit testable, and does not risk inventing brand or generic equivalence, correcting misspellings, or merging medications on partial string similarity, all of which could silently hide a real documentation inconsistency instead of surfacing it.

**Trade-offs**

Pros

- Fully reproducible and unit testable without any external service
- Cannot silently merge genuinely different medications
- No dependency on an AI provider being available or affordable at analysis time

Cons

- Will not catch a conflict where a document uses a materially different name for the same medication, such as a brand name where the list uses a generic name
- Requires new aliases to be added explicitly as they are identified, rather than inferred automatically

---

# Decision 13: Narrow Assumption for the Unsupported Medication List Entry Rule

**Decision**

Only generate an unsupported_medication_list_entry finding when at least one of the documents selected for the analysis has a document_type of medication_list or medication_reconciliation_form.

**Reasoning**

This finding type asserts that a medication in the user's list is not supported by the selected documents. That assertion is only safe if the selected documents can reasonably be expected to mention every current medication. A visit note, progress note, or discharge summary is not expected to re-list every medication a patient takes, so its silence proves nothing. A medication list or medication reconciliation form is different: both document types exist specifically to represent the current medication list, so silence there is meaningful evidence. Restricting the rule this way avoids the false positives the underlying finding type is most at risk of producing.

**Trade-offs**

Pros

- Avoids flagging medications as unsupported based on documents that were never meant to be exhaustive
- Uses a signal, document_type, that already exists rather than inventing a new one

Cons

- The rule produces no findings at all for an analysis that only includes visit notes or similar documents, even if a medication genuinely appears nowhere else
- Depends on document_type being set accurately at upload time

---

# Decision 14: Two-Phase Commit Boundary for Reconciliation Runs

**Decision**

Commit an Analysis in two separate steps before its findings exist: first as pending, then as processing. Only the remaining work, discrepancy creation and the final completed or failed transition, is committed as one atomic unit.

**Reasoning**

The existing Analysis service already commits each status transition independently. A single all-encompassing transaction across the entire reconciliation run would mean that if reconciliation fails, there would be no Analysis row at all to mark as failed, since the transaction that created it would also roll back. Committing pending and processing durably first guarantees a record of the run exists no matter what happens afterward, while still keeping discrepancy creation and the completion or failure fields atomic with each other, so no completed analysis can exist with a mismatched or missing set of findings.

**Trade-offs**

Pros

- A failed reconciliation run always leaves a durable, explained record instead of no record at all
- No completed analysis can exist with partially created discrepancies or counts that do not match them
- Reuses the existing single-item commit functions rather than introducing a new transaction pattern

Cons

- Not a single database transaction for the entire run, so an external observer could see a processing analysis with no findings yet
- Relies on rollback correctly discarding any discrepancies staged before a late failure, which must be verified by test rather than guaranteed by a single wrapping transaction

---

# Future Decisions

Additional architectural decisions will be documented as the project evolves, including topics such as:

- Background job processing
- Caching
- AWS architecture
- Deployment strategy
- Monitoring
- Performance optimization