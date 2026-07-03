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

## Analysis

Represents one reconciliation run across selected clinical documents.

An analysis compares medication mentions across multiple documentation sources and stores the resulting summary and discrepancies.

### Fields

```text
id
user_id
summary
status
processing_time_ms
created_at
updated_at
```

### Field Notes

```text
status
```

Tracks whether the analysis is complete, processing, or failed.

Possible values:

```text
processing
complete
failed
```

### Relationships

```text
Analysis belongs to User
Analysis has many MedicationDiscrepancies
```

---

## MedicationDiscrepancy

Represents a potential medication reconciliation issue found during an analysis.

### Fields

```text
id
analysis_id
medication_name
normalized_name
source_document_a_id
source_document_b_id
discrepancy_type
severity
ai_explanation
recommendation
resolved
created_at
updated_at
```

### Field Notes

```text
source_document_a_id
source_document_b_id
```

Reference the two documents being compared.

Example:

```text
Medication List
Visit Note
```

```text
discrepancy_type
```

Describes the type of inconsistency.

Possible values:

```text
status_conflict
missing_from_source
dose_mismatch
frequency_mismatch
unclear_status
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
resolved
```

Tracks whether the user has reviewed or dismissed the discrepancy.

### Relationships

```text
MedicationDiscrepancy belongs to Analysis
MedicationDiscrepancy references two ClinicalDocuments
```

---

## Relationship Summary

```text
User
  1 ─── many ClinicalDocument

ClinicalDocument
  1 ─── many MedicationMention

User
  1 ─── many Analysis

Analysis
  1 ─── many MedicationDiscrepancy

MedicationDiscrepancy
  many ─── 2 ClinicalDocuments
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

Source A: Medication List
Status: discontinued

Source B: Visit Note
Status: active

Discrepancy Type: status_conflict

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

### MedicationMention instead of Medication

The system stores medication mentions rather than global medication records.

This is intentional because the core problem is not maintaining one perfect medication list. The core problem is identifying how the same medication is represented differently across documents.

### Discrepancies are stored separately

Medication discrepancies are stored as their own model because users may need to review, resolve, dismiss, or revisit them later.

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
- reconciliation analyses
- saved discrepancy results

The MVP does not support:

- real patient data
- HIPAA compliance
- full EHR workflows
- provider organizations
- patient demographics
- billing or insurance information