# AI Pipeline

## Overview

MedLens uses a large language model to read clinical documents and produce a medication-focused summary. The AI layer is responsible only for reading text and producing a summary. It does not compare documents, detect discrepancies, or make clinical decisions. Reconciliation is separate, deterministic backend logic that does not call an AI provider.

The validated summary is persisted as a completed Analysis, including the extracted medications and possible inconsistencies, so it can be retrieved later. See Persistence below and `docs/data-model.md` for what is stored.

---

## Provider Architecture

AI providers are implemented behind a common interface so that business logic never depends on a specific provider.

```text
app/ai/
    providers/
        base.py
        gemini_provider.py
    prompts.py
    schemas.py
    service.py
```

### AIProvider

`base.py` defines `AIProvider`, an abstract base class with one method:

```text
generate_summary(prompt: str) -> str
```

Every provider implementation exposes a `name` and a `model` attribute and raises a single exception type, `AIProviderError`, for every failure case: missing configuration, request failures, timeouts, invalid or empty responses, and unexpected exceptions. Callers only need to handle `AIProviderError`, regardless of which provider is active.

### AISummaryService

`service.py` defines `AISummaryService`, which depends only on the `AIProvider` interface, not on any concrete provider. It combines one or more clinical note strings into a prompt using `prompts.py`, sends the prompt to the injected provider, and parses and validates the provider's raw text response into a `ClinicalSummary` before returning it, along with which provider and model produced it.

```text
AISummaryService(provider: AIProvider)
    .summarize(clinical_notes: list[str]) -> AISummaryResult
```

The provider is responsible only for communicating with the model and returning its raw text. Parsing that text as JSON and validating it against `ClinicalSummary` is the service's responsibility, not the provider's, so a future provider only needs to return raw text and never needs to know about the response schema.

If the provider's response is not valid JSON, or does not match `ClinicalSummary`, `AISummaryService` raises `AIProviderError`. Callers, including the API route, only ever see `AIProviderError`, never a raw `json.JSONDecodeError` or `pydantic.ValidationError`.

`get_ai_summary_service()` is a small factory function that constructs the currently configured provider from application settings and wraps it in an `AISummaryService`. The API layer depends on this factory, not on `GeminiProvider` directly.

### Current Provider: Gemini

`gemini_provider.py` implements `GeminiProvider` using Google's `google-genai` SDK. The Gemini API key is read lazily, at request time rather than at construction time, so building the provider never fails. If the key is missing when a summary is actually requested, `generate_summary` raises `AIProviderError` with a clear message, which the API layer turns into a `503` response.

---

## Adding a Future Provider

To add another provider, such as OpenAI, MedGemma, or OpenBioLLM:

1. Create a new module under `app/ai/providers/`, for example `openai_provider.py`.
2. Implement a class that subclasses `AIProvider`, sets `name` and `model`, and implements `generate_summary(prompt: str) -> str`.
3. Raise `AIProviderError` for every failure case inside that method, rather than letting a provider-specific exception escape.
4. Update `get_ai_summary_service()` to construct the desired provider based on configuration.

No changes are needed to `AISummaryService`, the prompt template, the API route, or any other business logic. This is the reason the provider interface exists: the rest of the application only ever depends on `AIProvider`, never on a specific SDK or vendor.

---

## Prompt

The summary prompt is centralized in `prompts.py` as `SUMMARY_PROMPT_TEMPLATE`, built by `build_summary_prompt(clinical_notes: list[str])`. Each note is numbered in the prompt ("Note 1:", "Note 2:", ...) in the order it is passed in. The prompt instructs the model to return a single JSON object with three fields: `medications` (one entry per medication *per note it is mentioned in* - the same medication mentioned in more than one note gets a separate entry for each, with name, dosage, route, frequency, status, notes, and `source_note`, the 1-indexed number of the note that entry came from), `possible_inconsistencies` (a list of plain-language descriptions of places where the notes disagree with each other, without attempting to resolve the disagreement), and `summary` (a short, clinically focused summary limited to medication-related information). The field names in the prompt match the `ClinicalSummary` schema exactly, so the shape the model is asked for and the shape that is validated are defined only once, in `schemas.py`. `source_note` is what lets each persisted `MedicationMention` be attached to its true source document instead of a placeholder (Issue #152; see `docs/architecture.md`'s Analysis Creation Pipeline).

The provider also requests JSON output using Gemini's structured output support (`response_mime_type="application/json"` on `GenerateContentConfig`), so the response is constrained to well-formed JSON at the API level, not only by the wording of the prompt. This does not pin down the exact JSON shape at the SDK level (`response_schema` is not set); the shape is described in the prompt text and enforced afterward by `ClinicalSummary`, so the schema does not need to be defined twice.

---

## Response Schema

`schemas.py` defines the validated shape of an AI response.

```text
Medication
    name: str
    dosage: str | None
    route: str | None
    frequency: str | None
    status: str | None
    notes: str | None
    source_note: int | None

ClinicalSummary
    medications: list[Medication]
    possible_inconsistencies: list[str]
    summary: str
```

Both models set `model_config = ConfigDict(extra="forbid")`. A response containing a field outside this shape, at either the top level or within a medication entry, fails validation rather than being silently accepted with the extra data dropped. This is a deliberate choice: an extra field means the model did not follow the prompt's contract, which is treated the same as any other invalid response.

`ClinicalNoteSummaryResponse`, the API response model, extends `ClinicalSummary` with `provider` and `model`, so the validated shape and the API response shape are defined once and stay in sync.

Validation happens in `AISummaryService._parse_response`, using `ClinicalSummary.model_validate_json(raw_response)`. Pydantic v2 parses the JSON and validates it in the same call, so malformed JSON and schema violations are both reported as the same `pydantic.ValidationError`, which the service catches and converts to `AIProviderError`.

---

## Persistence

`app/services/analysis_result_service.py` defines `persist_analysis_result(db, analysis, clinical_summary, provider, model)`, which stores a validated `ClinicalSummary` as the completed result of an Analysis. This module has no knowledge of Gemini or any provider; it only knows about the validated `ClinicalSummary` shape and the database models. Keeping persistence separate from `AISummaryService` means the service that validates AI output never touches a database session, and the module that touches the database never talks to a provider.

Each medication in `clinical_summary.medications` becomes one `AnalysisMedicationMention` row, and each string in `clinical_summary.possible_inconsistencies` becomes one `AnalysisInconsistency` row, both linked to the given Analysis. Neither model is matched against the user's Medication list or read by the reconciliation service; they are AI-extracted observations only. See `docs/data-model.md` for the full field list and why these are separate models from `MedicationMention` and `MedicationDiscrepancy`.

`persist_analysis_result` stages the new rows with `db.add()` but does not commit them itself. It delegates to the existing `mark_analysis_completed`, whose own commit persists the staged mentions and inconsistencies together with the completed Analysis fields (status, `completed_at`, `provider`, `model_name`, `summary`) in one transaction. `total_findings` and the severity counts are always set to zero here, since this path creates no `MedicationDiscrepancy` rows.

### Orchestration

`POST /ai/summarize` orchestrates the full flow:

1. Create the Analysis as `pending`, validating that every requested document exists and belongs to the caller (`create_analysis`). If this fails, no Analysis is created, and the request fails with `404` before anything else runs.
2. Mark it `processing` (`mark_analysis_processing`).
3. Call `AISummaryService.summarize()` to get a validated `ClinicalSummary`.
4. Call `persist_analysis_result()` to store the mentions, inconsistencies, and completed Analysis fields.

If step 3 or step 4 raises, the route rolls back the session, discarding anything staged but not yet committed, and calls `mark_analysis_failed` with a sanitized message, the same message returned to the caller. This mirrors the two-phase commit pattern already used by the reconciliation service: `pending` and `processing` are each committed durably on their own, so a failure always leaves an explained record, while the actual work (creating child rows, then completing) is one atomic unit.

---

## Configuration

The Gemini API key and model are read from environment variables, never hardcoded.

```text
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.0-flash
```

`GEMINI_API_KEY` is optional at the application level. The backend starts normally without it. A request to `POST /ai/summarize` made while the key is missing fails gracefully with a `503` response rather than a crash.

---

## API

### POST /ai/summarize

Purpose

Summarizes one or more of the authenticated user's clinical documents using the configured AI provider, and persists the result as a completed Analysis.

Authentication requirements

Requires a valid Bearer token, as described in `docs/api.md`.

Request body

```json
{
  "clinical_document_ids": [1, 2]
}
```

Success response

`201 Created`

```json
{
  "analysis_id": 7,
  "provider": "gemini",
  "model": "gemini-2.0-flash",
  "medications": [
    {
      "name": "Lisinopril",
      "dosage": "10 mg",
      "route": "oral",
      "frequency": "once daily",
      "status": "active",
      "notes": null
    }
  ],
  "possible_inconsistencies": [],
  "summary": "..."
}
```

`medications`, `possible_inconsistencies`, and `summary` are the provider's response, parsed and validated against `ClinicalSummary`, then persisted. `analysis_id` identifies the Analysis created for this request. As of Issue #148, the extracted medications are also reconciled against the patient's medication list as part of this same request - see `docs/architecture.md`'s Analysis Creation Pipeline and Reconciliation Engine sections; this response body itself is unchanged by that.

Error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: a requested document does not exist or does not belong to the current user. No Analysis is created in this case.
- `422 Unprocessable Entity`: the request body fails validation, for example an empty `clinical_document_ids` list.
- `503 Service Unavailable`: the AI provider could not produce a usable response, or persistence failed, including a missing API key, a request failure, a timeout, malformed JSON, or a response that does not match `ClinicalSummary`. The Analysis (already created by this point) is marked `failed` with the same message returned in the response.

---

### GET /ai/analyses/{analysis_id}

Purpose

Retrieves a previously created Analysis belonging to the authenticated user, including its persisted `AnalysisMedicationMention` and `AnalysisInconsistency` rows. Read-only: it does not call an AI provider, run reconciliation, or modify the Analysis in any way.

Authentication requirements

Requires a valid Bearer token, as described in `docs/api.md`.

Success response

`200 OK`. See `docs/api.md` for the full response body.

`medication_mentions` and `possible_inconsistencies` are returned sorted by ascending `id`. This ordering is decided when the response is built (in `sorted()` calls in the route), not by `get_analysis_for_user` itself and not via an `order_by` on the relationship, because rows persisted together in one `persist_analysis_result` transaction can share an identical `created_at` (Postgres's `now()` is constant for the duration of a transaction), so `id` is the only field guaranteed to reflect insertion order. Using `sorted()` to build new lists, rather than sorting `analysis.medication_mentions` and `analysis.possible_inconsistencies` in place, leaves the ORM-managed relationship collections on the loaded `Analysis` untouched. Both collections are loaded with `selectinload` rather than `joinedload`, since eagerly joining two independent one-to-many relationships at once would produce a cartesian product.

`error_message` reflects the same sanitized message persisted on the Analysis by `mark_analysis_failed` (see Orchestration above), and is `null` for any analysis that is not `failed`. This endpoint does not generate or reformat that message; it only exposes the value already stored on the model, so it carries the same guarantee as `POST /ai/summarize`'s `503` response: no stack trace, provider exception, `ValidationError` detail, raw AI output, or SQL error is ever included.

Error responses

- `401 Unauthorized`: missing or invalid access token.
- `404 Not Found`: the analysis does not exist or does not belong to the current user. Both cases return the same response so a caller cannot use this endpoint to probe for the existence of another user's analysis.

---

## Logging

The Gemini provider logs which provider and model were used, request duration, and success or failure. `AISummaryService` logs a validation failure with the provider, model, and the number of validation errors. In every case, only the standard `logging` module and these metadata fields are used. Clinical note contents, prompts, raw model responses, and the detailed contents of a `pydantic.ValidationError` are never logged, since validation error details can echo back fragments of the model's response.

---

## Limitations

- The AI response itself (medication names, dosages, etc.) is never checked for internal consistency by the AI layer - `possible_inconsistencies` is the model's own observation, not a deterministic check. Comparison against the user's Medication list is deterministic backend logic, not part of the AI layer - see `docs/architecture.md`'s Reconciliation Engine section for how it runs (as of Issue #148, automatically, during the same request).
- Only Gemini is implemented today. OpenAI, MedGemma, and OpenBioLLM are planned future providers, added behind the same `AIProvider` interface.
