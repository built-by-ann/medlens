# Data Model

The core idea is that the same medication shows up in many documents (medication lists, visit notes, discharge summaries) and doesn't always agree. MedLens stores **what each document says** (`MedicationMention`) separately from **the patient's medication list** (`Medication`), and records disagreements as `MedicationDiscrepancy`.

For exact columns, see `backend/app/models/`.

```text
User
 └── Patient
        ├── Medication
        ├── ClinicalDocument
        │      └── MedicationMention
        └── Analysis ──*──*── ClinicalDocument   (analysis_clinical_documents)
               ├── MedicationDiscrepancy ──▶ Medication? / MedicationMention? / User? (resolved_by)
               ├── AnalysisMedicationMention
               └── AnalysisInconsistency
```

## Ownership

`User` owns `Patient` through `Patient.user_id`. Everything else is owned **only** through `patient_id`; there is no `user_id` on medications, documents, or analyses. Routes enforce this via `get_owned_patient`.

This is the result of a staged migration from user-owned to patient-owned data:

1. Add `patient_id` and backfill it. Reuse the user's single active patient, or create a "Legacy Patient". Fail if the choice is ambiguous.
2. Cut routes over to `/patients/{id}/...`.
3. Drop `user_id` and make `patient_id` `NOT NULL`.

The backfill migration uses frozen `sa.table()` shadows so it still runs on a fresh database.

## Entities

### User
`email`, `hashed_password`, `name`, `username`.

- `username` is nullable at the DB level, so older accounts keep working. Registration requires it, but that rule lives in the request schema.
- It must be 3 to 30 characters from `[A-Za-z0-9_.]`.
- Uniqueness is case-insensitive via a functional unique index on `lower(username)`. The value is stored exactly as typed, and multiple NULLs are allowed.
- Login always uses email.

### Patient
`first_name`, `last_name`, `date_of_birth`, `external_mrn` (optional, unused), `status`, `notes`.

`status` is `active` or `archived`. Archiving is a soft delete and only happens through `DELETE`. There is no un-archive.

### ClinicalDocument
`document_type`, `title`, `raw_text`, `file_name`, `file_type` (`manual_entry` | `txt` | `pdf` | `csv`), `storage_key`, `content_type`, `file_size_bytes`.

- `raw_text` is always present. It's what the AI reads.
- The three storage fields are null together for pasted text and for documents uploaded before file storage existed (their bytes were never saved).
- `storage_key` is a backend-relative path or key, never a URL and never exposed via the API.
- `analysis_count` is a computed property.

### MedicationMention
What one document says about one medication: `clinical_document_id`, `medication_name`, `normalized_name`, `dose`, `route`, `frequency`, `status`, `confidence`, `context_text`.

During analysis, these are created from AI output and attached to the right source document via the AI's `source_note`. A mention falls back to the lowest-id document only if `source_note` is missing or invalid. Older analyses aren't retroactively corrected.

### Medication
The patient's list: `medication_name`, `dose`, `route`, `frequency`, `status`, `source` (`patient_reported`, `reconciliation`, ...), `notes`. Entered by the provider, or created and updated by resolving discrepancies. Both paths go through `medication_service`.

### Analysis
One run over a set of documents.

- `status`: `pending` → `processing` → `completed` | `failed`
- `started_at`, `completed_at`, `error_message` (sanitized)
- `summary`, `provider`, `model_name`
- `total_findings` and `high_`/`medium_`/`low_severity_findings`: separate integer columns, frozen when the run completes
- `document_count`: computed property

A `processing_time_ms` column was dropped because it can be derived from the two timestamps.

### AnalysisMedicationMention / AnalysisInconsistency
The AI's raw output for one run, scoped to the Analysis. These are kept separate from `MedicationMention` so the reconciliation pipeline's model didn't need to change.

- `AnalysisMedicationMention` uses `dosage` (the AI schema's name) where `MedicationMention` uses `dose`.
- `AnalysisInconsistency` is free text with no severity or type.

### MedicationDiscrepancy
One deterministic finding: `analysis_id`, `medication_id?`, `medication_mention_id?`, `discrepancy_type`, `severity`, `title`, `ai_explanation`, `recommendation`, `expected_value`, `observed_value`, and the resolution fields.

- `medication_id` and `medication_mention_id` are both nullable because a finding may have only one side. Both use **`ON DELETE SET NULL`** so findings outlive deleted evidence (Decision 10).
- `discrepancy_type`: `missing_from_medication_list`, `discontinued_status_conflict`, `dose_conflict`, `route_conflict`, `frequency_conflict`, `status_conflict`, `unsupported_medication_list_entry`
- `severity`: `low`, `medium`, `high`. Assigned from a fixed mapping.
- `resolution_status`: `open` → `resolved` | `dismissed`. This is one-way; a second attempt returns 409. `reviewed` exists in the enum but nothing sets it.
- **Audit fields** (`resolution_action`, `resolved_by_user_id`, `resolved_at`, `resolution_note`) are set together on resolution. They are columns rather than a history table because a finding can only be resolved once. `resolved_by_user_id` is `ON DELETE SET NULL`.
- `resolution_action` is just `add_medication`, `update_medication`, or `dismiss`. UI labels like "Mark Discontinued" are `update_medication` with a preset value.
- The original finding fields never change after resolution.

## Example

```text
Lisinopril: list says discontinued, visit note says active
→ status_conflict, expected "discontinued", observed "active"
```

## Not Modeled

Encounters, organizations, provider entities, medication ontologies, general audit logs, billing, or real patient data.
