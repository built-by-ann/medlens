# Data Model

## Overview

MedLens is designed around the idea that medication information can appear across multiple clinical documentation sources and may not remain consistent across all of them.

The data model focuses on storing clinical documents, extracting medication mentions from those documents, and identifying discrepancies between medication information found in different sources.

---

## Core Concept

Medication information may appear in:

- medication lists
- visit notes
- discharge summaries
- after-visit summaries
- progress notes
- medication reconciliation forms
- patient-entered medication records

MedLens treats each of these as a **ClinicalDocument**.

AI is used to extract structured medication information from each document. The application then compares extracted medication mentions across documents to identify possible reconciliation issues.

---

## Entity Relationship Diagram

```text
User
 │
 └── Patient
        ├── Medication        (via /patients/{id}/medications)
        ├── ClinicalDocument  (via /patients/{id}/clinical-documents)
        │      └── MedicationMention
        └── Analysis          (via /patients/{id}/analyses)
               ├── MedicationDiscrepancy
               ├── AnalysisMedicationMention
               └── AnalysisInconsistency
```

Sprint 3.5 migrated MedLens from a User-owned data model to a Patient-owned one, across seven issues:

- **Issue #126** introduced `Patient` on its own, with only a `User` relationship.
- **Issue #128** gave `Medication`, `ClinicalDocument`, and `Analysis` each a nullable `patient_id`, backfilled every existing row to a patient, and added the corresponding `Patient.medications` / `Patient.clinical_documents` / `Patient.analyses` relationships. Their original `user_id`/`user` were left untouched for this issue - both ownership paths coexisted temporarily, with every route and service still reading `user_id` only.
- **Issue #129** moved Medication's routes and services over to reading `patient_id` for authorization, nested under `/patients/{patient_id}/medications`.
- **Issue #130** repeated the same cutover for ClinicalDocument and Analysis, nested under `/patients/{patient_id}/clinical-documents` and `/patients/{patient_id}/analyses` respectively, and updated `medication_reconciliation_service` to load a patient's medications by `patient_id` instead of `user_id`. The old flat `/clinical-documents` and `/ai/summarize`/`/ai/analyses` routes were removed.
- **Issues #131/#132** built the patient-centered clinical workflow and provider dashboard on top of this - UI work, no further ownership changes.
- **Issue #133** removed the transitional compatibility layer entirely: `user_id` is now gone from `Medication`, `ClinicalDocument`, and `Analysis` (column dropped, `User.medications`/`User.clinical_documents`/`User.analyses` relationships removed), and `patient_id` on all three was tightened from nullable to `NOT NULL`, since it is now the sole ownership column and every row has always had one. **This is the final state** - ownership for these three resources exists solely through `Patient`; `User` is used only for authentication and for owning `Patient` directly (`Patient.user_id`).

See Design Decisions for the backfill strategy, the Medication/ClinicalDocument/Analysis cutover, and the final cleanup.

---

## Entities

## User

Represents an authenticated user of the application.

### Fields

```text
id
email
hashed_password
name
created_at
updated_at
```

### Relationships

```text
User has many Patients
```

`Medication`, `ClinicalDocument`, and `Analysis` are reached only through `Patient` (`Patient.medications` / `Patient.clinical_documents` / `Patient.analyses`) - `User` has no direct relationship to any of them (see Issue #133 in Design Decisions).

---

## Patient

Represents a patient chart owned by a provider (User). Introduced in Sprint 3.5 (Issue #126) as the first step of a staged migration toward a patient-centered data model. `Medication`, `ClinicalDocument`, and `Analysis` all reference Patient via `patient_id`, the sole ownership column for all three as of Issue #133 - see Design Decisions.

### Fields

```text
id
user_id
first_name
last_name
date_of_birth
external_mrn
status
notes
created_at
updated_at
```

### Field Notes

```text
external_mrn
```

An optional external medical-record-number or identifier, for a future integration with an outside records system. Not read or written by anything today.

```text
status
```

Tracks whether the patient chart is active or archived.

Possible values:

```text
active
archived
```

New patients start as `active`. Archiving is a soft delete: the row is never removed, only marked `archived`. There is currently no way to reverse an archive back to `active`. `status` cannot be set at creation or changed through the update endpoint - it changes only through the archive action.

```text
notes
```

Optional free-text notes about the patient. May be null. Distinct from a ClinicalDocument, which represents actual clinical documentation.

### Relationships

```text
Patient belongs to User
Patient has many Medications
Patient has many ClinicalDocuments
Patient has many Analyses
```

---

## ClinicalDocument

Represents any uploaded or entered documentation source that may contain medication information.

ClinicalDocument is owned by `Patient`: every API route and service function scopes and authorizes by `patient_id`, the sole ownership column - there is no `user_id` on this table. See Design Decisions.

An `analysis_count` property (`len(self.analyses)`) is computed on the model rather than stored as a column, added in Issue #146 so the frontend can show how many analyses a document has been included in - the same pattern as `Analysis.document_count`.

Examples:

- medication list
- visit note
- discharge summary
- after-visit summary
- progress note
- medication reconciliation form

### Fields

```text
id
patient_id
document_type
title
raw_text
file_name
file_type
created_at
updated_at
```

### Field Notes

```text
patient_id
```

Added in Sprint 3.5 (Issue #128), the sole column every route and service uses for ownership and authorization since Issue #130, and `NOT NULL` since Issue #133 - every row has always had one, since creation has always required an already-resolved, already-owned Patient.

```text
document_type
```

Describes the type of document, such as `medication_list`, `visit_note`, or `discharge_summary`.

```text
raw_text
```

Stores extracted or pasted document text.

```text
file_name
```

Stores the uploaded file name if the document came from an upload.

```text
file_type
```

Stores file format information such as `txt`, `pdf`, or `manual_entry`.

### Relationships

```text
ClinicalDocument belongs to Patient
ClinicalDocument has many MedicationMentions
```

---

## MedicationMention

Represents one medication reference extracted from a clinical document.

This model does not represent a universal medication record. Instead, it represents what one document says about one medication.

### Fields

```text
id
clinical_document_id
medication_name
normalized_name
dose
frequency
route
status
confidence
context_text
created_at
updated_at
```

### Field Notes

```text
medication_name
```

The medication name as written in the document.

```text
normalized_name
```

A cleaned or standardized version used for comparison.

Example:

```text
Metformin HCl → metformin
Glucophage → metformin
```

```text
status
```

Represents what the document appears to say about the medication.

Possible values:

```text
active
discontinued
started
changed
unknown
```

```text
confidence
```

Represents the model's confidence in the extracted medication mention.

```text
context_text
```

Stores the sentence or phrase from the original document that supports the extraction.

### Relationships

```text
MedicationMention belongs to ClinicalDocument
```

---

## Medication

Represents one medication in a patient's self-maintained medication list.

Unlike MedicationMention, a Medication record is not extracted from a clinical document. It is entered directly by the provider on the patient's behalf, independent of any document, and is not tied to a document's confidence or context.

Medication is owned by `Patient`: every API route and service function scopes and authorizes by `patient_id`, the sole ownership column - there is no `user_id` on this table. See Design Decisions.

### Fields

```text
id
patient_id
medication_name
dose
route
frequency
status
source
notes
created_at
updated_at
```

### Field Notes

```text
patient_id
```

Added in Sprint 3.5 (Issue #128), the sole column every route and service uses for ownership and authorization since Issue #129, and `NOT NULL` since Issue #133 - every row has always had one, since creation has always required an already-resolved, already-owned Patient.

```text
source
```

Describes where the medication entry came from, such as `patient_reported` or `manual_entry`.

```text
notes
```

Optional free-text notes about the medication. May be null.

### Relationships

```text
Medication belongs to Patient
```

---

## Analysis

Represents one analysis run across a set of clinical documents.

An analysis tracks who initiated it, which documents it covers, its progress through a status lifecycle, summary counts of what it found, and its results. This model only records the run and its outcome; it does not itself compare medication mentions or produce them.

An analysis can be completed by either of two separate entry points into the same underlying reconciliation engine, and its stored results differ depending on which one produced it:

- `run_medication_reconciliation` compares Medication against already-persisted MedicationMention rows using deterministic rules and produces MedicationDiscrepancy rows, with total_findings and the severity counts reflecting what it found. Nothing in the API calls this entry point directly today (see Design Decisions).
- The AI summary service (`POST /patients/{patient_id}/analyses`) reads clinical documents directly and produces AnalysisMedicationMention and AnalysisInconsistency rows, an AI observation of what the documents say. As of Issue #148, it also persists each extracted medication as a real MedicationMention and runs the *same* reconciliation engine against it, producing MedicationDiscrepancy rows here too - total_findings and the severity counts reflect real reconciliation output for this path as well, not a hardcoded zero. See Design Decisions and `docs/architecture.md`'s Analysis Creation Pipeline.

Analysis is owned by `Patient`: every API route and service function scopes and authorizes by `patient_id`, the sole ownership column - there is no `user_id` on this table. See Design Decisions.

### Fields

```text
id
patient_id
status
started_at
completed_at
error_message
summary
total_findings
high_severity_findings
medium_severity_findings
low_severity_findings
provider
model_name
created_at
updated_at
```

### Field Notes

```text
patient_id
```

Added in Sprint 3.5 (Issue #128), the sole column every route and service uses for ownership and authorization since Issue #130, and `NOT NULL` since Issue #133 - every row has always had one, since creation has always required an already-resolved, already-owned Patient.

```text
status
```

Tracks the analysis through its lifecycle.

Possible values:

```text
pending
processing
completed
failed
```

New analyses start as `pending`. `processing` marks the run as underway, `completed` and `failed` are terminal states.

```text
started_at
completed_at
```

Record when processing began and when the run reached a terminal state, whether by completing or failing. Both are null until the corresponding transition happens.

```text
error_message
```

Set when an analysis fails, describing why. Cleared if an analysis is later marked completed.

```text
summary
```

An optional narrative summary of the analysis, stored as text. May hold a structured JSON string if the reconciliation service chooses that format, but the column itself is untyped text, consistent with the rest of this schema.

```text
total_findings
high_severity_findings
medium_severity_findings
low_severity_findings
```

Counts of discrepancies found during the run, broken out by severity. Stored as individual integer columns rather than a JSON structure, since the set of counts is small, fixed, and needs to support simple database queries and updates. Default to 0 and are not expected to be negative.

```text
provider
model_name
```

Record which AI provider and model produced the analysis, when applicable. Both are nullable, since not every analysis path is required to use an AI provider.

### Relationships

```text
Analysis belongs to Patient
Analysis has many MedicationDiscrepancies
Analysis has many AnalysisMedicationMentions
Analysis has many AnalysisInconsistencies
Analysis references many ClinicalDocuments
```

The relationship to ClinicalDocument is many to many: an analysis typically covers more than one document, and the same document can be included in more than one analysis over time. This is implemented with an association table, analysis_clinical_documents, rather than a foreign key on either side. See Design Decisions.

---

## AnalysisMedicationMention

Represents one medication as extracted by the AI summary service for a single analysis run.

This is distinct from MedicationMention, which belongs to a ClinicalDocument and is read by the deterministic reconciliation service. AnalysisMedicationMention belongs to an Analysis instead, and is not matched against the user's Medication list. It is a record of what the AI observed when summarizing the selected documents, nothing more.

### Fields

```text
id
analysis_id
medication_name
dosage
route
frequency
status
notes
created_at
updated_at
```

### Field Notes

```text
dosage
```

Named to match the field the AI summary prompt and its validated response schema use. MedicationMention, an unrelated model, uses `dose` for the same concept.

### Relationships

```text
AnalysisMedicationMention belongs to Analysis
```

---

## AnalysisInconsistency

Represents one possible inconsistency as observed by the AI summary service.

This is an unstructured AI observation, not a deterministic finding. It has no severity, no discrepancy type, and no reference to a Medication or MedicationMention. Structured, deterministic findings are represented by MedicationDiscrepancy, produced by the reconciliation service, not by this model.

### Fields

```text
id
analysis_id
description
created_at
updated_at
```

### Relationships

```text
AnalysisInconsistency belongs to Analysis
```

---

## MedicationDiscrepancy

Represents a potential medication reconciliation issue found during an analysis.

A discrepancy references at most one Medication and at most one MedicationMention, since a finding may only have one side of the comparison. A medication mentioned in a document but missing from the medication list has a MedicationMention and no Medication. A medication list entry with no supporting document has a Medication and no MedicationMention.

Rows in this table are produced by the medication reconciliation service, a deterministic backend process, not an AI call. Severity is assigned from a single, centralized mapping from discrepancy type to severity, described in docs/architecture.md.

`GET /patients/{patient_id}/analyses/{analysis_id}` exposes these rows via `medication_discrepancies` (Issue #148). As of Issue #46, each one also nests the Medication or MedicationMention its `medication_id`/`medication_mention_id` points to (the mention's own source ClinicalDocument nested one level further, as a minimal citation) directly in the response, so a caller can render supporting evidence without a second request. See docs/api.md.

### Fields

```text
id
analysis_id
medication_id
medication_mention_id
discrepancy_type
severity
title
ai_explanation
recommendation
expected_value
observed_value
resolution_status
created_at
updated_at
```

### Field Notes

```text
medication_id
medication_mention_id
```

Reference the medication list entry and the extracted mention being compared. Both are nullable, and a discrepancy is not required to have both. Deleting the referenced Medication or MedicationMention sets the corresponding field to null rather than deleting the discrepancy.

```text
discrepancy_type
```

Describes the type of inconsistency.

Possible values:

```text
missing_from_medication_list
discontinued_status_conflict
dose_conflict
route_conflict
frequency_conflict
status_conflict
unsupported_medication_list_entry
```

```text
severity
```

Represents how important the discrepancy may be for review.

Possible values:

```text
low
medium
high
```

```text
title
```

A short, human-readable summary of the finding.

```text
expected_value
observed_value
```

Store the specific values being compared, such as a status or dose recorded in the medication list versus the value observed in a document.

```text
resolution_status
```

Tracks how the user has responded to the discrepancy.

Possible values:

```text
open
reviewed
resolved
dismissed
```

### Relationships

```text
MedicationDiscrepancy belongs to Analysis
MedicationDiscrepancy references Medication
MedicationDiscrepancy references MedicationMention
```

---

## Relationship Summary

```text
User
  1 ─── many Patient

Patient
  1 ─── many Medication

Patient
  1 ─── many ClinicalDocument

Patient
  1 ─── many Analysis

ClinicalDocument
  1 ─── many MedicationMention

Analysis
  1 ─── many MedicationDiscrepancy

Analysis
  1 ─── many AnalysisMedicationMention

Analysis
  1 ─── many AnalysisInconsistency

MedicationDiscrepancy
  many ─── 1 Medication

MedicationDiscrepancy
  many ─── 1 MedicationMention

Analysis
  many ─── many ClinicalDocument
```

---

## Example Workflow

1. A user uploads a medication list.
2. The application stores it as a ClinicalDocument.
3. AI extracts medication mentions from the document.
4. The user uploads a visit note.
5. The application stores it as another ClinicalDocument.
6. AI extracts medication mentions from the visit note.
7. The user runs an analysis comparing both documents.
8. MedLens identifies medications that appear inconsistent across sources.
9. The analysis and discrepancies are saved for review.

---

## Example Discrepancy

```text
Medication: Lisinopril

Medication List Status: discontinued
Visit Note Status: active

Discrepancy Type: status_conflict
Expected Value: discontinued
Observed Value: active

Explanation:
Lisinopril is marked as discontinued in the medication list but appears as an active medication in the visit note.

Recommendation:
Review whether the medication list should be updated or whether the visit note contains outdated information.
```

---

## Design Decisions

### ClinicalDocument instead of MedicationSource

The system uses `ClinicalDocument` rather than `MedicationSource` because medication information usually appears inside broader clinical documents, not only structured medication lists.

This keeps the model flexible enough to support visit notes, discharge summaries, after-visit summaries, and medication lists.

### MedicationMention versus Medication

The system stores medication mentions rather than treating extracted document data as a global medication record.

This is intentional because the core reconciliation problem is not maintaining one perfect medication list. The core problem is identifying how the same medication is represented differently across documents.

Medication is a separate model representing the user's own, self-maintained medication list. It exists independently of document extraction and is not a source for reconciliation. The two models serve different purposes: MedicationMention captures what a document says, while Medication captures what the user says.

### Discrepancies are stored separately

Medication discrepancies are stored as their own model because users may need to review, resolve, dismiss, or revisit them later.

### MedicationDiscrepancy references Medication and MedicationMention

The original MedicationDiscrepancy design compared two ClinicalDocuments directly, before Medication existed as a model. Now that Medication represents the user's own list, reconciliation findings compare a medication list entry against an extracted mention rather than two documents. The nullable medication_id and medication_mention_id fields replace the earlier document references, since every supported finding type is a list-versus-mention comparison rather than a document-versus-document comparison. Document context remains reachable through medication_mention_id, since a MedicationMention belongs to a ClinicalDocument.

### Analysis references ClinicalDocument through an association table

An analysis typically covers more than one clinical document, and the same document can be reused across more than one analysis over time, for example when a user re-runs reconciliation after uploading a new document. A foreign key on either Analysis or ClinicalDocument can only represent one of those two directions, so the relationship uses an association table, analysis_clinical_documents, instead. The association table has no columns of its own beyond the two foreign keys, so it uses a composite primary key rather than a surrogate id, unlike every other table in this schema.

### Analysis drops processing_time_ms in favor of started_at and completed_at

The original Analysis model stored a single processing_time_ms duration. Once started_at and completed_at exist, the duration is derivable from the two, and storing both timestamps preserves more information than a single computed duration would. The analyses table held no rows when this change was made, so no data was lost.

### Analysis summary counts are individual integer columns

total_findings, high_severity_findings, medium_severity_findings, and low_severity_findings are stored as separate integer columns rather than a single JSON structure. The set of counts is small and fixed, and individual columns are simpler to query, default, and update than a JSON document would be for the same purpose.

### AnalysisMedicationMention and AnalysisInconsistency instead of reusing MedicationMention

Persisting AI summary results needed a model scoped to Analysis, but MedicationMention already existed, scoped to ClinicalDocument, with a `dose` field, and is load-bearing for the reconciliation service. Renaming or repurposing it would have broken a working, tested pipeline for a reason unrelated to that pipeline. AnalysisMedicationMention and AnalysisInconsistency are new models instead, matching the field names the AI schema and prompt already use, so the persisted record needs no translation from what was validated. Neither model is matched against Medication or read by the reconciliation service.

### Patient introduced without linking ClinicalDocument, Medication, or Analysis

Patient is added on its own, with only a `User` relationship, rather than migrating ClinicalDocument, Medication, and Analysis onto it in the same change. Each of those three models already has a `user_id` foreign key backing live, tested functionality; moving them to `patient_id` requires a data backfill (one legacy Patient per existing User) and touches every route and service that currently scopes by `user_id`. Bundling that with Patient's introduction would make this change more than additive. Splitting it into its own issue keeps this one reversible and low-risk, and lets the later migration issue focus solely on the cutover.

A corollary, true at the time: `Patient` couldn't yet declare `medications`, `clinical_documents`, or `analyses` relationships, since SQLAlchemy's `relationship()` requires a real foreign key or join condition to configure against, and none of the three models had `patient_id` yet. Issue #128 (below) added it, and these relationships are now real.

### Issue #128: patient_id added to Medication, ClinicalDocument, and Analysis, with a same-migration backfill

Rather than adding `patient_id` as a bare nullable column and leaving every pre-existing row unset, the same migration backfills it for every row that existed before Patient did (`app/services/patient_backfill_service.py`, called from the Alembic migration that adds the column). Leaving old rows with a null `patient_id` indefinitely would mean two ownership models silently disagreeing about who owns old data - the whole point of this migration is that after it runs, `patient_id` is populated everywhere, even though `user_id` is still what every route and service actually reads today.

**Backfill algorithm**, per user with at least one legacy (patient_id IS NULL) medication, clinical document, or analysis:

- Exactly one **active** Patient exists for that user → every legacy row is assigned to it. (Archived patients don't count - an archived chart isn't a reasonable home for data nobody chose to attach to it.)
- Zero Patients exist → a placeholder Patient is created (`first_name: "Legacy"`, `last_name: "Patient"`, `date_of_birth: 1900-01-01`, `status: "active"`, `notes: "Automatically created during patient migration."`), and every legacy row is assigned to it.
- More than one active Patient exists → the migration **fails** for that user (`AmbiguousPatientBackfillError`) rather than guessing which patient owns the data. Since this runs inside Alembic's transactional DDL, failing partway rolls back the schema changes too, leaving the database exactly as it was.
- A user with multiple patients but *no* legacy data at all is left alone entirely - there's no ownership decision to make for a user who never used the old Medication/ClinicalDocument/Analysis features under a single implicit "patient" (themselves).

The backfill is idempotent by construction rather than by an explicit dedup flag: re-running finds no legacy rows left (every one already has a `patient_id`), so a user who already got a placeholder Patient created for them now has exactly one active Patient, not zero, and the "exactly one" branch reuses it rather than creating a second one.

`user_id` is deliberately left in place and unmodified by this migration on all three tables - both ownership paths coexist so that every existing route, service, and the frontend keep working exactly as before. Issues #129/#130 move routes over to reading `patient_id`, and Issue #133 (below) is where `user_id` is finally dropped.

### Issue #129: Medication becomes the first resource to cut over to patient-scoped authorization

Issue #128 gave Medication a `patient_id` column but left every route and service reading `user_id`. Issue #129 is the cutover: `GET/POST/PATCH/DELETE /medications` moved to `GET/POST/PATCH/DELETE /patients/{patient_id}/medications`, and `medication_service.py` no longer accepts or filters by `user_id` at all - every function takes `patient_id` (or, for creation, the already-resolved `Patient` itself).

A new shared FastAPI dependency, `get_owned_patient` (`app/api/deps.py`), resolves and authorizes `patient_id` once - a route simply cannot receive a `Patient` it doesn't own. Every medication route depends on it rather than re-implementing the ownership check, the same way every route already depended on `get_current_user`. This is the pattern the rest of Sprint 3.5 will reuse for ClinicalDocument and Analysis.

`Medication.user_id` remained a real, populated, `NOT NULL` column at this point (Issue #129 explicitly did not drop it), vestigial from the API's point of view - nothing read it for authorization from here on. It was derived automatically from the resolved patient (`medication.user_id = patient.user_id`) purely so the `NOT NULL` constraint kept being satisfied without asking API callers to supply a value that would be redundant. Issue #133 (below) is where the column itself was finally dropped.

`MedicationResponse` changed to expose `patient_id` instead of `user_id` - the one deliberate response-schema change in this migration (Issue #128 explicitly avoided any schema change, since its routes hadn't moved yet; here, moving the routes is the entire point, so the response reflecting the new ownership model is the correct contract, not scope creep).

---

### Issue #130: ClinicalDocument and Analysis repeat the Medication cutover

Issue #130 applies Issue #129's exact pattern to the two remaining User-scoped resources. `GET/POST /clinical-documents`, `/clinical-documents/upload-txt`, `/clinical-documents/upload-pdf`, and `GET/DELETE /clinical-documents/{id}` moved to the equivalent `/patients/{patient_id}/clinical-documents...` routes; `/ai/summarize` and `GET/GET/DELETE /ai/analyses...` were replaced by `/patients/{patient_id}/analyses...` (the old `app/api/routes/ai.py` was deleted and replaced by `app/api/routes/analyses.py`). Both `clinical_document_service.py` and `analysis_service.py` now take `patient_id` (or an already-resolved `Patient`) instead of `user_id`, reusing the same `get_owned_patient` dependency Issue #129 introduced.

`create_analysis` validates its requested `clinical_document_ids` with a single scoped query (`ClinicalDocument.id.in_(ids), ClinicalDocument.patient_id == patient.id`), so a request naming a document that doesn't exist, belongs to a different user, or belongs to a different patient of the *same* user is rejected in exactly the same way - no analysis is created and no partial state is left behind. This is the same one-query pattern used for authorization elsewhere, applied to a document *set* rather than a single row.

`medication_reconciliation_service.run_medication_reconciliation` (confirmed not wired to any live route as of this issue) took a `user_id` and used it to load the medications to reconcile against (`Medication.filter(user_id == ...)`). Since Medication itself moved to `patient_id` in Issue #129, this one remaining `user_id` read would have silently pulled in medications from every one of a user's patients, not just the one being reconciled. Issue #130 changes its signature to take a `Patient` and filters by `Medication.patient_id == patient.id` instead, even though the function has no caller yet - leaving it reading `user_id` here would have been a live bug in an otherwise-migrated codebase the moment it was wired up.

`ClinicalDocumentResponse.user_id` and `AnalysisSummaryResponse`/`AnalysisDetailResponse`'s implicit ownership field are replaced with `patient_id`, matching Issue #129's `MedicationResponse` change for the same reason. The test-only `AnalysisResponse` schema (still `user_id`, used only by `test_analysis.py`/`test_medication_reconciliation_service.py`, never by any route) is deliberately left untouched, since changing it would be schema churn with no live caller to justify it.

`ClinicalDocument.user_id` and `Analysis.user_id` were retained at this point exactly as `Medication.user_id` was - real, `NOT NULL`, populated, vestigial from the API's point of view, and derived from the resolved patient rather than accepted independently.

---

### Issue #133: user_id dropped from Medication, ClinicalDocument, and Analysis

The final Sprint 3.5 migration issue. Issues #129/#130 had already moved every route and service off `user_id` for these three tables; the column had been read by nothing for two full issues, kept only so its `NOT NULL` constraint didn't block inserts. This issue removes it outright:

- **Models**: `user_id` and its `user` relationship are gone from `Medication`, `ClinicalDocument`, and `Analysis`. `patient_id` is tightened from nullable to `NOT NULL` on all three, now that it's the only ownership column - there was never actually a row without one (Issue #128's backfill guaranteed that from day one), so this only makes the schema honest about a guarantee the application already relied on. `User.medications`, `User.clinical_documents`, and `User.analyses` are removed too; `User.patients` is the only relationship `User` has left to any of this data.
- **Alembic migration** (`3ef685b18302`): drops the `user_id` foreign key and column and applies the `NOT NULL` constraint to `patient_id`, on all three tables. Data-preserving by construction - it only removes an already-unread column and tightens a constraint every row already satisfied; `patient_id` itself is never touched. The downgrade re-derives `user_id` from `patients.user_id` via `patient_id` (a plain `UPDATE ... FROM patients`) rather than adding the column back with nothing to populate it, which Postgres would reject on any table with existing rows.
- **A migration-history correction**: the earlier `599e0487bb6d` migration (Issue #128) originally called `app.services.patient_backfill_service.backfill_patient_ids`/`clear_patient_ids`, which queried the *live* ORM models' `user_id` attribute. That is exactly the situation `patient_backfill_service.py`'s own docstring warned about ("if any of these five models is later renamed or restructured, this module... would fail if ever replayed from scratch against an empty database") - and this issue is that restructuring. `599e0487bb6d` was updated in place to use lightweight, local `sa.table()` shadows frozen at that point in schema history instead of importing today's models, so `alembic upgrade head` still runs correctly against a brand-new database. `patient_backfill_service.py` and its test were deleted, since nothing else ever called them.
- **Services**: `medication_service.py`, `clinical_document_service.py`, and `analysis_service.py` no longer derive or assign `user_id` on create - there is nothing left to derive it onto.
- **Schemas**: the test-only `AnalysisResponse` (the last schema anywhere still exposing `user_id`, left alone in Issue #130 specifically because it was dead code, not because it was correct) is deleted outright, not just stripped of the field. Its two call sites (`test_analysis.py`, `test_medication_reconciliation_service.py`) were rewritten against `AnalysisDetailResponse`, the schema real routes actually use.
- **Frontend**: required no changes at all. `types/api.ts`'s `ClinicalDocument`, `Medication`, and `AnalysisSummary` types already used only `patient_id` (Issues #129/#130); the only `user_id` field left anywhere in the frontend is `Patient.user_id`, which is correct and untouched.

Verified end to end on a real database: applied `3ef685b18302` against the dev database (row counts unchanged before/after), downgraded and confirmed `user_id` was correctly re-derived to match every row's `patient.user_id`, re-upgraded, and separately ran the entire migration chain from an empty database to confirm the frozen `599e0487bb6d` logic still works when replayed from scratch.

---

### Issue #148: medication reconciliation wired into analysis creation

Every model, service function, and persistence path used here already existed - `MedicationDiscrepancy`, `MedicationMention`, `build_discrepancy_findings`, `create_medication_discrepancies`, and `run_medication_reconciliation` all predate this issue. What was missing was any caller: `run_medication_reconciliation` has never been invoked by an API route, and `POST /patients/{patient_id}/analyses` (the AI summary flow, the only analysis-creation path a provider can actually reach) never populated `MedicationMention` or called the reconciliation engine, so `total_findings` and the severity counts on that path were always hardcoded zero.

This issue closes that gap without changing any of the above: `medication_reconciliation_service.py`'s shared "build findings, persist them, count severities" logic was extracted from `run_medication_reconciliation`'s body into a new `reconcile_medications` helper (identical behavior, now callable from two places instead of duplicated). A new `reconcile_ai_extracted_medications` function bridges the AI flow's extracted medications into real `MedicationMention` rows - attached to the selected document with the lowest id, since the AI's response has no per-document attribution to preserve (see `docs/architecture.md`) - then calls the same `reconcile_medications` helper. `analysis_result_service.py`'s `persist_analysis_result` calls this bridge and uses its real counts instead of the zeros it hardcoded before. No schema, model, or migration changed; `AnalysisDetailResponse` gained a `medication_discrepancies` field (reusing the existing `MedicationDiscrepancyResponse` schema) so `GET /patients/{patient_id}/analyses/{analysis_id}` can return what reconciliation actually found.

---

## Future Extensions

Patient (see above) has moved from this list into the main Entities section, since it now exists.

Other potential future models include:

```text
Encounter
Organization
Provider
MedicationOntology
AnalysisDocument
ResolutionHistory
AuditLog
```

These are intentionally excluded from the MVP to keep the first version focused and buildable.

---

## MVP Scope

The MVP data model supports:

- authenticated users
- uploaded or pasted clinical documents
- AI-extracted medication mentions
- user-maintained medication lists
- reconciliation analyses
- saved discrepancy results
- persisted AI summary results, including extracted medications and possible inconsistencies

The MVP does not support:

- real patient data
- HIPAA compliance
- full EHR workflows
- provider organizations
- patient demographics
- billing or insurance information