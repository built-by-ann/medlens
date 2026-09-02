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

MedLens migrated from a User-owned data model to a Patient-owned one: `Patient` was introduced first, with only a `User` relationship; `Medication`, `ClinicalDocument`, and `Analysis` were then backfilled onto it, cut over to patient-scoped routes and authorization, and finally had their original `user_id` columns dropped. **This is the final state**: ownership for these three resources exists solely through `Patient`; `User` is used only for authentication and for owning `Patient` directly (`Patient.user_id`). See Design Decisions, below, for the full backfill strategy and cutover sequence.

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
username
created_at
updated_at
```

### Field Notes

```text
username
```

Optional and independent of authentication: login always uses email/password, regardless of whether a username is set (see Design Decisions). Nullable at the database level so an account that predates usernames continues to work unchanged, with `username: null`; `POST /auth/register` requires one for every new account, but that requirement lives in the request schema (`UserCreate`), not the column itself.

Unique **case-insensitively**: enforced by a functional index on `lower(username)` (see the Alembic migration) rather than a plain column-level unique constraint, which would only catch an exact-case duplicate. The value is still stored and returned exactly as the user typed it; only the *uniqueness check* folds case, not the stored value itself, so `jdoe` and `JDoe` cannot coexist but a user who registers as `JDoe` still sees `JDoe`, never `jdoe`, everywhere it's displayed.

Format is validated in the same request schema, independent of the uniqueness check: 3-30 characters, containing only `a-z`, `A-Z`, `0-9`, `_`, and `.`.

### Relationships

```text
User has many Patients
```

`Medication`, `ClinicalDocument`, and `Analysis` are reached only through `Patient` (`Patient.medications` / `Patient.clinical_documents` / `Patient.analyses`); `User` has no direct relationship to any of them (see Design Decisions).

---

## Patient

Represents a patient chart owned by a provider (User). `Medication`, `ClinicalDocument`, and `Analysis` all reference Patient via `patient_id`, the sole ownership column for all three; see Design Decisions for the migration that got the schema here.

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

New patients start as `active`. Archiving is a soft delete: the row is never removed, only marked `archived`. There is currently no way to reverse an archive back to `active`. `status` cannot be set at creation or changed through the update endpoint; it changes only through the archive action.

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

ClinicalDocument is owned by `Patient`: every API route and service function scopes and authorizes by `patient_id`, the sole ownership column; there is no `user_id` on this table. See Design Decisions.

An `analysis_count` property (`len(self.analyses)`) is computed on the model rather than stored as a column, so the frontend can show how many analyses a document has been included in, the same pattern as `Analysis.document_count`.

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
storage_key
content_type
file_size_bytes
created_at
updated_at
```

### Field Notes

```text
patient_id
```

The sole column every route and service uses for ownership and authorization, `NOT NULL` since every row has always had one, since creation has always required an already-resolved, already-owned Patient.

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

```text
storage_key
content_type
file_size_bytes
```

Identifies and describes the original uploaded file in whichever `StorageService` backend is configured (see `docs/architecture.md`): `storage_key` is a local filesystem path or an S3 object key, never a URL, so switching backends or renaming a bucket never requires touching stored data. All three are nullable together, and null for the same two reasons: a document created via pasted text (`POST /patients/{patient_id}/clinical-documents`) never had a file to begin with, and any document created before this column existed has nothing to backfill it with, since the original bytes for those rows were never persisted anywhere (see Design Decisions). `storage_key` is never exposed over the API (`docs/api.md`): it is an internal detail the download endpoint resolves on the document's behalf, not something a client should ever need to construct a request around.

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

Medication is owned by `Patient`: every API route and service function scopes and authorizes by `patient_id`, the sole ownership column; there is no `user_id` on this table. See Design Decisions.

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

The sole column every route and service uses for ownership and authorization, `NOT NULL` since every row has always had one, since creation has always required an already-resolved, already-owned Patient.

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
- The AI summary service (`POST /patients/{patient_id}/analyses`) reads clinical documents directly and produces AnalysisMedicationMention and AnalysisInconsistency rows, an AI observation of what the documents say. It also persists each extracted medication as a real MedicationMention and runs the *same* reconciliation engine against it, producing MedicationDiscrepancy rows here too: total_findings and the severity counts reflect real reconciliation output for this path, not a hardcoded zero. See Design Decisions and `docs/architecture.md`'s Analysis Creation Pipeline.

Analysis is owned by `Patient`: every API route and service function scopes and authorizes by `patient_id`, the sole ownership column; there is no `user_id` on this table. See Design Decisions.

A `document_count` property (`len(self.clinical_documents)`) is computed on the model rather than stored as a column, so the Analysis Results page's AI Summary metadata can show how many documents an analysis covers, the same pattern as `ClinicalDocument.analysis_count`.

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

The sole column every route and service uses for ownership and authorization, `NOT NULL` since every row has always had one, since creation has always required an already-resolved, already-owned Patient.

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

`GET /patients/{patient_id}/analyses/{analysis_id}` exposes these rows via `medication_discrepancies`. Each one also nests the Medication or MedicationMention its `medication_id`/`medication_mention_id` points to (the mention's own source ClinicalDocument nested one level further, as a minimal citation) directly in the response, so a caller can render supporting evidence without a second request. See docs/api.md.

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
resolution_action
resolved_by_user_id
resolved_at
resolution_note
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

`reviewed` is defined but not currently set by anything: a discrepancy transitions directly from `open` to `resolved` or `dismissed` via the resolve endpoint below (Issue: Complete Medication Reconciliation Workflow). There is no "re-open" action: once a discrepancy leaves `open`, `POST .../discrepancies/{discrepancy_id}/resolve` rejects a second attempt with `409 Conflict` (see docs/api.md) rather than allowing it to be resolved again or reverted.

```text
resolution_action
resolved_by_user_id
resolved_at
resolution_note
```

Added by the discrepancy resolution workflow (Issue: Complete Medication Reconciliation Workflow) to record a full audit trail directly on the discrepancy, rather than a separate history table; see Design Decisions. All four are set together, only by `resolve_discrepancy` (`app/services/medication_discrepancy_service.py`), and stay `null` for as long as `resolution_status` is `open`.

`resolution_action` is one of `add_medication`, `update_medication`, `dismiss` (`ResolutionAction`, `app/schemas/medication_discrepancy.py`), the actual operation a provider performed, distinct from and more specific than `resolution_status`. Deliberately only three values rather than one per UI action ("Mark Discontinued," "Mark Active," "Edit Manually," and "Update Medication" are all `update_medication`, differing only in which field values the request supplies); see Design Decisions.

`resolved_by_user_id` references `users.id`, `ON DELETE SET NULL` and indexed, the same nullable-on-delete pattern already used for `medication_id`/`medication_mention_id` on this table, so a discrepancy's resolution audit trail survives the resolving user's account being deleted, just with that one piece of attribution now missing. `resolved_by` (the relationship) has no reverse `back_populates` on `User`, since nothing needs to list "every discrepancy this user has resolved" today.

`resolved_at` is a timezone-aware timestamp, set once and never updated afterward (resolving is one-way). `resolution_note` is optional freeform text, a provider's rationale, independent of any medication field.

### Relationships

```text
MedicationDiscrepancy belongs to Analysis
MedicationDiscrepancy references Medication
MedicationDiscrepancy references MedicationMention
MedicationDiscrepancy references User (resolved_by)
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

A corollary, true at the time: `Patient` couldn't yet declare `medications`, `clinical_documents`, or `analyses` relationships, since SQLAlchemy's `relationship()` requires a real foreign key or join condition to configure against, and none of the three models had `patient_id` yet. The backfill migration described below added it, and these relationships are now real.

### Patient-owned data model: backfill and cutover

`Medication`, `ClinicalDocument`, and `Analysis` moved from being owned directly by `User` to being owned by `Patient`. The migration ran in stages so it stayed reversible and low-risk at each step, rather than as one large change:

1. **Add `patient_id`, backfilled.** Each of the three tables gained a `patient_id` column, populated for every pre-existing row in the same migration (`app/services/patient_backfill_service.py`) rather than left null. Leaving old rows unset would have meant two ownership models silently disagreeing about who owns old data; the migration's whole point is that `patient_id` is populated everywhere once it completes, even before any route reads it.

   **Backfill algorithm**, per user with at least one legacy (`patient_id IS NULL`) medication, clinical document, or analysis:

   - Exactly one **active** Patient exists for that user: every legacy row is assigned to it. (Archived patients don't count; an archived chart isn't a reasonable home for data nobody chose to attach to it.)
   - Zero Patients exist: a placeholder Patient is created (`first_name: "Legacy"`, `last_name: "Patient"`, `date_of_birth: 1900-01-01`, `status: "active"`, `notes: "Automatically created during patient migration."`), and every legacy row is assigned to it.
   - More than one active Patient exists: the migration **fails** for that user (`AmbiguousPatientBackfillError`) rather than guessing which patient owns the data. Since this runs inside Alembic's transactional DDL, failing partway rolls back the schema changes too, leaving the database exactly as it was.
   - A user with multiple patients but *no* legacy data at all is left alone entirely: there's no ownership decision to make for a user who never used the old Medication/ClinicalDocument/Analysis features under a single implicit "patient" (themselves).

   The backfill is idempotent by construction rather than by an explicit dedup flag: re-running finds no legacy rows left (every one already has a `patient_id`), so a user who already got a placeholder Patient created for them now has exactly one active Patient, not zero, and the "exactly one" branch reuses it rather than creating a second one. `user_id` was left in place and unmodified at this stage on all three tables, so both ownership paths coexisted while every route, service, and the frontend kept working unchanged.

2. **Cut routes and services over to `patient_id`.** `Medication` moved first: `GET/POST/PATCH/DELETE /medications` became `GET/POST/PATCH/DELETE /patients/{patient_id}/medications`, and `medication_service.py` stopped accepting or filtering by `user_id` entirely. A shared FastAPI dependency, `get_owned_patient` (`app/api/deps.py`), resolves and authorizes `patient_id` once, so a route simply cannot receive a `Patient` it doesn't own, and every medication route depends on it rather than re-implementing the check, the same way every route already depended on `get_current_user`. `ClinicalDocument` and `Analysis` followed the identical pattern: their flat routes (`/clinical-documents...`, `/ai/summarize`, `/ai/analyses...`) were replaced by the patient-nested equivalents, and both services took `patient_id` (or an already-resolved `Patient`) instead of `user_id`, reusing the same `get_owned_patient` dependency. `create_analysis` validates its requested `clinical_document_ids` with a single scoped query (`ClinicalDocument.id.in_(ids), ClinicalDocument.patient_id == patient.id`), so a request naming a document that doesn't exist, belongs to a different user, or belongs to a different patient of the *same* user is rejected the same way: no analysis is created and no partial state is left behind. `medication_reconciliation_service.run_medication_reconciliation` (not wired to any live route) was updated to take a `Patient` and filter by `Medication.patient_id == patient.id`, even before it had a caller, so it would not have silently pulled in medications from every one of a user's patients the moment it was wired up. `MedicationResponse`, `ClinicalDocumentResponse`, and `AnalysisSummaryResponse`/`AnalysisDetailResponse` all expose `patient_id` instead of `user_id`. Each table's `user_id` column stayed real, populated, and `NOT NULL` through this stage, derived automatically from the resolved patient purely so the constraint kept being satisfied without asking API callers to supply a redundant value, vestigial from the API's point of view, but not yet dropped.

3. **Drop `user_id`.** Once every route and service had moved off it, `user_id` and its `user` relationship were removed outright from `Medication`, `ClinicalDocument`, and `Analysis`, and `patient_id` was tightened from nullable to `NOT NULL` on all three: there was never actually a row without one, so this only makes the schema honest about a guarantee the application already relied on. `User.medications`, `User.clinical_documents`, and `User.analyses` were removed too; `User.patients` is the only relationship `User` has left to any of this data. The Alembic migration (`3ef685b18302`) is data-preserving by construction: it only removes an already-unread column and tightens a constraint every row already satisfied, and its downgrade re-derives `user_id` from `patients.user_id` via `patient_id` rather than adding the column back with nothing to populate it. The earlier backfill migration (`599e0487bb6d`) was also updated in place, from querying the live ORM models' `user_id` attribute to lightweight, local `sa.table()` shadows frozen at that point in schema history, so `alembic upgrade head` still runs correctly against a brand-new database even after the models it originally referenced changed shape; `patient_backfill_service.py` and its test were deleted once nothing called them anymore. The test-only `AnalysisResponse` schema (the last schema anywhere still exposing `user_id`) was deleted outright, with its two test call sites rewritten against `AnalysisDetailResponse`, the schema real routes use. The frontend required no changes: its `ClinicalDocument`, `Medication`, and `AnalysisSummary` types already used only `patient_id`.

This is the final state: ownership for these three resources exists solely through `Patient`.

---

### Medication reconciliation wired into analysis creation

`MedicationDiscrepancy`, `MedicationMention`, `build_discrepancy_findings`, `create_medication_discrepancies`, and `run_medication_reconciliation` all predate this integration; what was missing was a caller on the path a provider can actually reach. `POST /patients/{patient_id}/analyses` (the AI summary flow) now populates `MedicationMention` and calls the reconciliation engine as part of the same request, rather than leaving `total_findings` and the severity counts hardcoded to zero. `medication_reconciliation_service.py`'s shared "build findings, persist them, count severities" logic lives in a `reconcile_medications` helper, callable both from this flow and from `run_medication_reconciliation` directly, rather than duplicated between them. A `reconcile_ai_extracted_medications` function bridges the AI flow's extracted medications into real `MedicationMention` rows before calling that shared helper. `AnalysisDetailResponse` exposes the result via a `medication_discrepancies` field (reusing the existing `MedicationDiscrepancyResponse` schema), so `GET /patients/{patient_id}/analyses/{analysis_id}` returns what reconciliation actually found.

---

### Document-level provenance for AI medication mentions

Each AI-extracted medication is attributed to the specific document it came from, not just the lowest-id document among those selected for an analysis. `Medication` (`app/ai/schemas.py`) carries an optional `source_note: int | None` field, the 1-indexed position of the "Note N" (see `app/ai/prompts.py`) the AI reports this medication came from, and the prompt template asks for one medication entry per (medication, note) occurrence, each tagged with its `source_note`, rather than one aggregate entry per medication name. `ordered_clinical_documents` (`app/services/analysis_service.py`) sorts `analysis.clinical_documents` by id ascending, the one deterministic order shared between where the prompt numbers notes (`app/api/routes/analyses.py`) and where a reported note number is mapped back to a real document (`_resolve_source_document_id`, `medication_reconciliation_service.py`), since the many-to-many `analysis_clinical_documents` relationship has no inherent ordering guarantee of its own. `_resolve_source_document_id` falls back to the lowest-id selected document only when `source_note` is missing or out of range, a defensive fallback for a malformed response, not the normal path. `build_discrepancy_findings` and every `_find_*` helper needed no change for this: they already group `MedicationMention` rows by normalized medication name regardless of how many there are or which document each is attached to.

Analyses created before per-document attribution existed keep whatever (possibly inexact) `clinical_document_id` their mentions were given at creation time; this is not retroactively corrected, since the original note text isn't stored per mention and which document a historical mention actually came from can't be recovered after the fact.

---

### Discrepancy resolution audit trail as columns on MedicationDiscrepancy, not a separate history table

The resolution workflow needed a complete audit trail (who resolved a discrepancy, when, what action, and an optional note) that never loses the original finding data. Rather than introduce a new `ResolutionHistory`/`AuditLog` model (both still listed under Future Extensions below, for a genuinely separate concept, a general-purpose change log across many resource types), four nullable columns were added directly to `MedicationDiscrepancy`: `resolution_action`, `resolved_by_user_id`, `resolved_at`, `resolution_note`. A discrepancy is resolved exactly once (there is no re-open/undo action; see `resolution_status` above), so there is only ever one resolution event per row to record; a separate one-to-many history table would model a "many resolutions over time" scenario that can't actually happen here. This keeps the audit trail queryable in the same request that already loads the discrepancy (no join, no N+1), and keeps every original reconciliation-run field (`title`, `ai_explanation`, `expected_value`, `observed_value`, ...) on the same row, untouched by resolution, satisfying "the discrepancy... must remain a permanent, complete record" directly, rather than needing to reconstruct it by joining against a history table.

`ResolutionAction` deliberately has only three values (`add_medication`, `update_medication`, `dismiss`), not one per UI-level action. The frontend's discrepancy-type-specific labels ("Mark Discontinued," "Mark Active," "Update Medication," "Edit Manually") name distinct actions per type, but every one of those, once a `Medication` already exists to modify, is the same operation: apply whichever fields the request supplies to that `Medication`. "Mark Discontinued" is `update_medication` with `status: "discontinued"`; "Edit Manually" is `update_medication` with provider-typed values instead of AI-suggested ones. The backend has no way to distinguish those two requests, nor any reason to: keeping the enum minimal avoids one API-level enum value per frontend button, consistent with `docs/api.md`'s existing "reuse existing services, keep reconciliation logic centralized" direction for this workflow, and pushes "which value to suggest for this button" entirely to the frontend, which already has the discrepancy's own evidence (`medication`, `medication_mention`) to derive a suggestion from.

The `resolve_discrepancy` service function (`app/services/medication_discrepancy_service.py`) is additive to the existing reconciliation architecture, not a parallel workflow: it calls the same `create_medication`/`update_medication` functions `app/services/medication_service.py` already exposed to the medication-management routes, so there is exactly one place `Medication` rows are ever created or mutated, regardless of whether the request came from `PatientMedicationsPage`'s own form or from resolving a discrepancy.

---

### Username as a nullable column with case-insensitive uniqueness

`User` has a `username` column, nullable at the database level so an account that predates usernames keeps working with no backfill and no downtime; the migration (`86d736611ffb`) only added a column and an index, touching no existing row. `POST /auth/register` requires one for every new account, but that's a request-schema rule (`UserCreate.username: str`), not a database constraint; the column itself stays nullable indefinitely, since there's no plan to force existing accounts to pick one retroactively.

Uniqueness is enforced case-insensitively, which a plain `unique=True` column constraint cannot do: Postgres compares strings byte-for-byte for a standard unique index, so `jdoe` and `JDoe` would otherwise be treated as different values and be allowed to coexist, defeating the point of a human-facing handle meant to be unambiguous. The migration instead creates a **functional unique index** on `lower(username)`. This has two consequences worth being explicit about:

- The stored value is never lowercased. A user who registers as `JDoe` is stored, returned, and displayed as `JDoe` everywhere; only the *uniqueness check* folds case, not the data itself. Re-fetching the same username later and comparing it byte-for-byte to what the user originally typed will always match.
- NULLs are exempt from the uniqueness check entirely: Postgres never considers two NULLs equal in a unique index (functional or otherwise), so any number of accounts without a username can share `username IS NULL` with no conflict. This is exactly what "existing users continue working" requires, and it falls out of a standard Postgres behavior rather than needing special-case handling in application code.

The application layer (`app/services/user_service.py`'s `get_user_by_username`) queries with the same `lower(...)` comparison the index uses, so the friendly, request-time uniqueness check (`app/api/routes/auth.py`/`users.py` returning a `409` before anything touches the database's own constraint) and the database's own guarantee can never disagree about whether a given username is taken.

---

### File storage as an additive capability

File storage was added on top of the existing `raw_text`/AI-analysis pipeline, not as a replacement for a prior storage mechanism: before it existed, MedLens never persisted an uploaded document's original bytes anywhere: `upload-txt`/`upload-pdf`/`upload-csv` read the file into memory, extracted (or decoded) its text into `raw_text`, and discarded the bytes.

`storage_key`, `content_type`, and `file_size_bytes` are nullable for two reasons: a row that predates file storage has nothing to backfill them with (the original bytes for those documents were never captured, so there is nothing to retroactively upload even in principle), and a pasted-text document has no file at all, by design, regardless of when it was created.

`storage_key` deliberately holds a backend-relative identifier (a local path or an S3 key), never a full URL, the feature's own "do not store S3 URLs" requirement. This is what makes `docs/architecture.md`'s `StorageService` swap (local storage in development, S3 in production, chosen by one environment variable) transparent to the data already in Postgres: a `storage_key` written while `STORAGE_BACKEND=local` still means exactly the same thing if the backend is later switched to `s3` with the same key layout, since neither backend's key format encodes which backend produced it. (Switching backends after documents already exist under the other one is not itself supported by this issue; existing keys would need to be migrated to the new backend's storage, a data-migration concern distinct from the schema migration this issue makes.)

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