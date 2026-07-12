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
 ├── ClinicalDocument
 │      └── MedicationMention
 │
 ├── Medication
 │
 └── Analysis
        └── MedicationDiscrepancy
```

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
User has many ClinicalDocuments
User has many Medications
User has many Analyses
```

---

## ClinicalDocument

Represents any uploaded or entered documentation source that may contain medication information.

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
user_id
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
ClinicalDocument belongs to User
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

Represents one medication in a user's own, self-maintained medication list.

Unlike MedicationMention, a Medication record is not extracted from a clinical document. It is entered and owned directly by the user, independent of any document, and is not tied to a document's confidence or context.

### Fields

```text
id
user_id
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
source
```

Describes where the medication entry came from, such as `patient_reported` or `manual_entry`.

```text
notes
```

Optional free-text notes about the medication. May be null.

### Relationships

```text
Medication belongs to User
```

---

## Analysis

Represents one reconciliation run across a set of clinical documents.

An analysis tracks who initiated it, which documents it covers, its progress through a status lifecycle, summary counts of what it found, and the resulting discrepancies. It does not itself compare medication mentions; that comparison is the responsibility of the future reconciliation service. This model only records the run and its outcome.

### Fields

```text
id
user_id
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
Analysis belongs to User
Analysis has many MedicationDiscrepancies
Analysis references many ClinicalDocuments
```

The relationship to ClinicalDocument is many to many: an analysis typically covers more than one document, and the same document can be included in more than one analysis over time. This is implemented with an association table, analysis_clinical_documents, rather than a foreign key on either side. See Design Decisions.

---

## MedicationDiscrepancy

Represents a potential medication reconciliation issue found during an analysis.

A discrepancy references at most one Medication and at most one MedicationMention, since a finding may only have one side of the comparison. A medication mentioned in a document but missing from the medication list has a MedicationMention and no Medication. A medication list entry with no supporting document has a Medication and no MedicationMention.

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
  1 ─── many ClinicalDocument

ClinicalDocument
  1 ─── many MedicationMention

User
  1 ─── many Medication

User
  1 ─── many Analysis

Analysis
  1 ─── many MedicationDiscrepancy

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

---

## Future Extensions

Potential future models include:

```text
Patient
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

The MVP does not support:

- real patient data
- HIPAA compliance
- full EHR workflows
- provider organizations
- patient demographics
- billing or insurance information