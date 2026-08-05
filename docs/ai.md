# AI Architecture

## Overview

MedLens uses a large language model (Google Gemini) to read synthetic clinical documents and extract structured, medication-focused information: which medications are mentioned, their dosage/route/frequency/status as stated in the text, and a short clinical summary. That is the entire scope of what AI does in this application - it reads text and produces structured observations. It does not compare documents, decide whether two records conflict, or make a clinical decision of any kind.

Comparing those AI-extracted observations against a patient's actual medication list - the "reconciliation" in MedLens's name - is separate, deterministic backend logic that never calls an AI provider. This document exists to make that boundary, and the machinery on either side of it, explicit. See `docs/architecture.md` for where the AI layer sits in the application as a whole, `docs/api.md` for the exact HTTP contract of the endpoint that uses it, `docs/testing.md` for this project's general testing conventions, and `docs/design-decisions.md` for the reasoning behind the choices summarized here (referenced by number throughout).

---

## AI Philosophy

MedLens was inspired by research into medication documentation inconsistencies within electronic health records (see `README.md`'s Motivation section) - the premise is that the same medication is often documented slightly differently across a patient's various clinical notes, and surfacing those inconsistencies for a human to review is valuable even without resolving them automatically. AI is used for the one part of that problem language models are actually good at: reading unstructured clinical text and pulling out structured facts. Everything after that - deciding whether two structured facts actually conflict - is handled deterministically.

Concretely, in MedLens:

**AI is responsible for:**
- Reading clinical note text and identifying every medication mentioned.
- Extracting each mention's dosage, route, frequency, and status *as that specific note states them*.
- Noticing and describing places where notes appear to disagree with each other, without attempting to resolve the disagreement.
- Producing a short, clinically focused summary of the medication information across the provided notes.

**AI is explicitly not responsible for, and is never asked to do:**
- Diagnosing, or making any treatment recommendation. The prompt itself (`app/ai/prompts.py`) opens by stating this directly: *"You are assisting with clinical documentation review. You are not making clinical decisions, diagnoses, or treatment recommendations."*
- Deciding whether an extracted medication conflicts with the patient's medication list - that comparison is deterministic reconciliation (see Reconciliation Pipeline, below, and Decision 12 in `docs/design-decisions.md`).
- Resolving a disagreement it notices between notes - the prompt explicitly instructs it to describe a disagreement, never to decide which note is correct.
- Any fuzzy/semantic matching of medication names (e.g. inferring a brand name and a generic name refer to the same drug) - that would risk silently hiding a real documentation inconsistency instead of surfacing it, which is exactly what this application exists to catch.

This split is why "AI decisions vs. deterministic application logic" is a load-bearing distinction throughout this document, not just a phrase: every section below is written from one side of that line or the other.

---

## High-Level Architecture

```text
app/ai/
    providers/
        base.py             AIProvider interface, AIProviderError
        gemini_provider.py  GeminiProvider (the only implementation today)
    prompts.py               SUMMARY_PROMPT_TEMPLATE, build_summary_prompt()
    schemas.py                Medication, ClinicalSummary (the validated response shape)
    service.py                 AISummaryService, get_ai_summary_service()
```

Everything under `app/ai/` is responsible for exactly one thing: turning a list of clinical note strings into a validated `ClinicalSummary`. It has no knowledge of HTTP, the database, or reconciliation - `AISummaryService.summarize()` takes `list[str]` in and returns a plain dataclass out, nothing more.

```text
                     ┌─────────────────────────  app/ai/  (this document)  ─────────────────────────┐
                     │                                                                                │
 clinical note text  │   AISummaryService          AIProvider            Gemini API                  │
 (list[str])  ─────► │   .summarize()      ─────►  .generate_summary()  ─────►  (google-genai SDK)    │
                     │        │                          ▲                                            │
                     │        │ builds prompt via        │ GeminiProvider is the only                 │
                     │        │ prompts.py                │ concrete implementation today              │
                     │        ▼                                                                        │
                     │   raw JSON text  ──►  ClinicalSummary.model_validate_json()  ──►  validated     │
                     │                                                                    ClinicalSummary
                     └────────────────────────────────────────────────────────────────────────────────┘
                                                          │
                                                          ▼
              ┌──────────────────────  outside app/ai/ - deterministic  ──────────────────────┐
              │                                                                                 │
              │  persist_analysis_result()  →  MedicationMention rows  →  reconciliation engine │
              │  (app/services/)               (evidence)                  (build_discrepancy_   │
              │                                                             findings - no AI)    │
              │                                                                  │                │
              │                                                                  ▼                │
              │                                                     MedicationDiscrepancy rows    │
              └─────────────────────────────────────────────────────────────────────────────────┘
```

The boundary drawn above is exact, not approximate: nothing under `app/services/` imports from `app/ai/providers/`, and nothing under `app/ai/` imports SQLAlchemy or touches a database session. `AISummaryService` is testable with zero database access (see Testing, below); the reconciliation engine is testable with zero AI provider (Decision 12).

---

## Data Flow

The full request, from an HTTP call to a persisted result, is orchestrated by one route handler - `summarize_clinical_documents` in `app/api/routes/analyses.py`, behind `POST /patients/{patient_id}/analyses` (see `docs/api.md` for the full HTTP contract: request/response bodies, status codes, authentication). This section describes what that route does, in order; `docs/architecture.md`'s "Analysis Creation Pipeline" section has the equivalent diagram drawn from the reconciliation side and is the more detailed reference for everything from `persist_analysis_result` onward - this section does not repeat it, only frames where the AI layer's own responsibility ends.

1. **Create the Analysis as `pending`** (`create_analysis`) - validates that every requested `clinical_document_ids` entry exists and belongs to this patient. If any id is invalid, the request fails with `404` and no Analysis is created at all; nothing AI-related has happened yet.
2. **Mark it `processing`** (`mark_analysis_processing`), committed durably on its own (Decision 14) before any AI call is made.
3. **Build the prompt and call the provider** - the selected documents' `raw_text` is read in a fixed, deterministic order (`ordered_clinical_documents`, sorted by id - see Prompt Management below for why this order matters), and `AISummaryService.summarize()` is called with that list of note strings. *This is the only step in the whole pipeline that leaves the application process* - everything before and after is local computation.
4. **Persist the result** (`persist_analysis_result`) - stores the validated `ClinicalSummary`'s medications and inconsistencies as `AnalysisMedicationMention`/`AnalysisInconsistency` rows, then hands the extracted medications to the deterministic reconciliation engine (see Reconciliation Pipeline below), and finally marks the Analysis `completed` with the real findings and severity counts.

If step 3 or step 4 raises anything, the route rolls back the session (discarding anything staged but not committed) and calls `mark_analysis_failed` with a sanitized message - the same message returned to the caller as the `503` response body. See Error Handling, below, for exactly what "sanitized" means here.

---

## Provider Abstraction

`app/ai/providers/base.py` defines `AIProvider`, an abstract base class with one method:

```python
class AIProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def generate_summary(self, prompt: str) -> str: ...
```

and one exception type, `AIProviderError`, that every provider implementation raises for *every* failure case - missing configuration, a request failure, a timeout, an empty or invalid response, or any other unexpected exception. `AISummaryService` (and everything above it - the route, ultimately the API's `503` response) only ever needs to handle this one exception type, regardless of which provider is active.

**`GeminiProvider`** (`app/ai/providers/gemini_provider.py`) is the only concrete implementation today, built on Google's `google-genai` SDK. Two details worth being explicit about:

- The API key is checked lazily, *inside* `generate_summary`, not in `__init__`. Constructing a `GeminiProvider` (which happens on every request, via the factory below) always succeeds, even with no key configured; the key only matters, and only fails, when a summary is actually requested. This is what lets the backend start normally with no `GEMINI_API_KEY` set at all, and only fail the specific request that needs it.
- The underlying `genai.Client` is constructed lazily too, and cached on the instance (`self._client`) - not rebuilt on every call.

**`get_ai_summary_service()`** (`app/ai/service.py`) is the provider factory - a plain function, not a separate `factory.py` module:

```python
def get_ai_summary_service() -> AISummaryService:
    provider = GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)
    return AISummaryService(provider)
```

It is used as a FastAPI dependency (`Depends(get_ai_summary_service)` in `app/api/routes/analyses.py`), which is also the seam route-level tests use to substitute a fake provider via `app.dependency_overrides` (see Testing below). There is no separate "provider selection" configuration today - `get_ai_summary_service` always constructs a `GeminiProvider`; see Configuration below for exactly what is and isn't environment-configurable.

**Why this abstraction exists** (Decision 15, `docs/design-decisions.md`): the project intends to evaluate more than one provider over time (see README's roadmap - MedGemma, OpenBioLLM, and general provider benchmarking are listed as planned, not implemented). Behind this interface, adding one is a new class implementing one method and translating its own SDK's exceptions into `AIProviderError` - nothing in `AISummaryService`, the prompt template, or the API route needs to change. See Extending the AI Layer, below, for the concrete steps.

---

## Prompt Management

The entire prompt is one Python string constant, `SUMMARY_PROMPT_TEMPLATE`, in `app/ai/prompts.py`, filled in by one function:

```python
def build_summary_prompt(clinical_notes: list[str]) -> str: ...
```

**Inputs.** A `list[str]` of clinical note texts - nothing else. No patient metadata, no medication list, no prior analysis history, and no per-request customization of the prompt itself is ever passed in; the same fixed template is used for every request, for every patient. `build_summary_prompt` raises `ValueError` if given an empty list (there is nothing to summarize).

**Responsibilities.** `build_summary_prompt` does exactly one piece of work beyond string interpolation: it numbers each note in the order given (`"Note 1:"`, `"Note 2:"`, ...), joined by a separator. That numbering matters beyond formatting - the prompt asks the model to report which numbered note each extracted medication came from (`source_note`), and the reconciliation layer later maps that number back to a real `ClinicalDocument` id using the *exact same order* the documents were selected in when the prompt was built (`ordered_clinical_documents`, sorted by id ascending - see `docs/architecture.md`'s Analysis Creation Pipeline). Both call sites deliberately reuse one canonical order rather than each deriving their own.

**Location.** `prompts.py` is the single place any prompt text exists in the codebase - there is no prompt template elsewhere, no per-provider prompt variant, and no runtime prompt construction outside this one function.

**Design philosophy.** The prompt is a single static template with note interpolation, nothing more elaborate. To be explicit about what is *not* present, since it would be easy to assume otherwise: there are no few-shot examples, no chain-of-thought instructions, no temperature/sampling configuration, no retrieval-augmented context, and no per-request prompt variation of any kind. The instructions are direct and enumerated (five numbered rules - see the file itself for the exact wording), asking the model to: identify every medication with one entry per note it appears in; record fields only as that specific note states them, never inferring across notes; report `source_note`; describe (not resolve) disagreements between notes; and write a medication-focused summary. The prompt also explicitly asks for the response as JSON only, with no markdown fences or surrounding text - reinforced at the SDK level (see Structured Output, below).

---

## Structured Output

**Response format.** The prompt asks for a single JSON object with three top-level fields (`medications`, `possible_inconsistencies`, `summary`) whose shape matches `ClinicalSummary` (`app/ai/schemas.py`) field-for-field - deliberately, so the shape described to the model and the shape enforced afterward are defined once, in the Pydantic model, not twice. `GeminiProvider` additionally constrains the response using Gemini's own structured-output support:

```python
JSON_RESPONSE_CONFIG = GenerateContentConfig(response_mime_type="application/json")
```

This constrains the response to well-formed JSON at the API level (not just by asking nicely in the prompt text), but does **not** pin down the exact JSON *shape* - `response_schema` is not set. The shape is described only in the prompt and enforced only afterward, by Pydantic; defining it in two places (an SDK-level schema and a Pydantic model) was a deliberate non-choice, to avoid the two drifting out of sync with each other.

**Pydantic models** (`app/ai/schemas.py`):

```python
class Medication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    dosage: str | None = None
    route: str | None = None
    frequency: str | None = None
    status: str | None = None
    notes: str | None = None
    source_note: int | None = None

class ClinicalSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    medications: list[Medication]
    possible_inconsistencies: list[str]
    summary: str
```

Both set `extra="forbid"`: a response containing any field outside this shape, at either level, fails validation rather than silently dropping the extra data. This is deliberate (Decision 16) - an unexpected field means the model didn't follow the prompt's contract, and that is treated as an invalid response, not a partially-acceptable one.

**Parsing and validation** happen in one call, `AISummaryService._parse_response`:

```python
ClinicalSummary.model_validate_json(raw_response)
```

Pydantic v2 parses the JSON text and validates it against the schema in the same call, so malformed JSON (not valid JSON at all) and a schema violation (valid JSON, wrong shape) both surface as the same `pydantic.ValidationError` - one failure mode, one code path, rather than a separate `json.JSONDecodeError` case to handle differently.

**Error handling.** `AISummaryService` catches `ValidationError` and re-raises it as `AIProviderError("AI response failed validation")` - the same exception type every other provider failure uses (see Provider Abstraction, above), so the API route's error handling doesn't need to know or care whether a `503` came from a network failure or a malformed response. Only the *count* of validation errors is logged (`error.error_count()`), never the errors themselves or the raw response text - `ValidationError.errors()` can include fragments of the offending input, which could echo clinical note content back into the logs.

**Becoming application objects.** A validated `ClinicalSummary` is a plain in-memory Pydantic object with no knowledge of the database - turning it into persisted rows is `persist_analysis_result`'s job (`app/services/analysis_result_service.py`), entirely outside `app/ai/`: each `Medication` becomes one `AnalysisMedicationMention` row, each inconsistency string becomes one `AnalysisInconsistency` row, and (as of the reconciliation bridge described below) each medication is also persisted as a real `MedicationMention` for the reconciliation engine to compare against the patient's medication list. `ClinicalNoteSummaryResponse` (`app/ai/schemas.py`, the route's actual response model) extends `ClinicalSummary` with `analysis_id`, `provider`, and `model`, so the validated shape and the API response shape stay defined once - see `docs/api.md` for the full response body.

---

## Validation

To state each of these plainly, since the issue behind this document specifically asks not to describe behavior that doesn't exist:

| Concern | Behavior |
|---|---|
| **Schema validation** | Every provider response is validated against `ClinicalSummary` with `extra="forbid"` before it is trusted (Decision 6, Decision 16). Nothing bypasses this. |
| **Provider validation** | Every provider failure - configuration, network, timeout, empty response, or an SDK-specific exception - is normalized to `AIProviderError` inside the provider implementation (`GeminiProvider`), never left as a raw SDK exception for a caller to handle. |
| **Retry behavior** | **None exists.** A failed request (network error, timeout, malformed response, anything) fails the analysis immediately, once - there is no retry loop, no exponential backoff, and no re-prompting on a validation failure. |
| **Fallback behavior** | **None exists.** There is no second provider, no cached/default response, and no degraded mode - a Gemini failure is a failed analysis, reported as such. |
| **`AIProviderError` usage** | The single exception type raised by every provider for every failure, and by `AISummaryService` for a response validation failure. The API route (`app/api/routes/analyses.py`) catches `Exception` broadly around the whole AI-and-persistence sequence (not `AIProviderError` specifically) and uses a helper, `_safe_error_message`, to decide what the caller sees: an `AIProviderError`'s own message is passed through as-is (it's already been written to be safe to expose), while any other exception type is replaced with a generic `"Analysis failed due to an internal error (<ExceptionType>)."` - so an unexpected bug never leaks its own exception message to the API response, only `AIProviderError`'s deliberately-crafted ones do. |

---

## Reconciliation Pipeline

This is the deterministic half of the system - **no AI provider is called anywhere in this section.** `docs/architecture.md`'s "Analysis Creation Pipeline" has the authoritative full-detail walkthrough (which document each `MedicationMention` gets attached to, the exact staging/commit boundaries, etc.); this section states the AI/deterministic boundary plainly and points there for the rest.

```text
AI-extracted medications (ClinicalSummary.medications)
        │
        ▼
reconcile_ai_extracted_medications()      ◄── bridges the AI flow into reconciliation
  - persists each as a real MedicationMention row
  - attaches it to its true source document via `source_note`
        │
        ▼
reconcile_medications() / build_discrepancy_findings()      ◄── fully deterministic, no AI
  - normalizes medication names/fields (fixed rules + a small alias list, e.g. "po" → "oral")
  - compares the patient's Medication list against the MedicationMention evidence
  - produces MedicationDiscrepancy rows with a fixed severity mapping
        │
        ▼
persist_analysis_result() → mark_analysis_completed()
  - real severity counts, evidence-linked discrepancies, Analysis marked completed
```

| | AI decision | Deterministic application logic |
|---|---|---|
| Reads clinical note text and identifies medications mentioned | ✅ | |
| Records what a note *literally states* about dosage/route/frequency/status | ✅ | |
| Notices notes disagreeing with each other, without resolving it | ✅ | |
| Normalizes medication names/fields for comparison (whitespace, casing, aliases) | | ✅ (`app/services/medication_normalization.py`) |
| Decides whether an extracted mention conflicts with the patient's medication list | | ✅ (`build_discrepancy_findings`, Decision 12) |
| Assigns a discrepancy's severity | | ✅ (a fixed `SEVERITY_BY_DISCREPANCY_TYPE` mapping) |
| Attaches a mention to its true source document | | ✅ (`source_note`, reported by AI, resolved deterministically) |
| Decides whether a discrepancy is later resolved/dismissed | | ✅ (a human provider, via `POST .../resolve` - see `docs/api.md`) |

**Evidence generation.** Every `MedicationDiscrepancy` carries deterministic, template-generated `title`/`ai_explanation`/`expected_value`/`observed_value` fields (despite the field name `ai_explanation`, this text is generated by plain Python string formatting in `medication_reconciliation_service.py`, not by an AI call - a naming leftover from before the deterministic engine existed, not a description of how it currently works) and, on read, is enriched with the actual `MedicationMention`/`Medication` rows that produced it (see `docs/api.md`'s discrepancy-detail response) - a provider reviewing a finding sees exactly what evidence produced it, not just AI's summary of it.

**A second, currently-unwired entry point.** `run_medication_reconciliation` (`app/services/medication_reconciliation_service.py`) is a complete, independent way to run the same reconciliation engine directly against already-persisted `MedicationMention` rows, without going through the AI-summary flow at all. It is fully covered by its own tests (`tests/test_medication_reconciliation_service.py`), but - as of this audit - **no API route calls it**; the live `POST /patients/{patient_id}/analyses` endpoint only ever reaches reconciliation via `reconcile_ai_extracted_medications`. `docs/architecture.md` documents this explicitly as an existing, deliberate second entry point into the same shared logic (`reconcile_medications`), not dead code slated for removal - stated here so a reader auditing routes doesn't miss why a fully-tested function has no caller in `app/api/`.

---

## Configuration

```text
GEMINI_API_KEY=          # optional - see below
GEMINI_MODEL=gemini-2.5-flash
```

Read via `app/core/config.py`'s `Settings` (a `pydantic-settings` `BaseSettings`, loaded from `.env`/the environment):

- **`GEMINI_API_KEY`** (`Settings.gemini_api_key: str | None = None`) - optional at the application level. The backend starts normally with no key configured at all; only a request that actually needs to call Gemini fails, with a `503` and the message `"Gemini API key is not configured"` (see Error Handling, below). This is unlike the storage backend's own `S3_BUCKET_NAME`/`AWS_REGION`, which fail application *startup* if missing while `STORAGE_BACKEND=s3` (`docs/architecture.md`'s Storage Abstraction section) - the AI layer has no equivalent fail-fast validator, since there is exactly one configuration (Gemini, always) and a missing key is a normal, expected local-development state, not a misconfiguration to catch early.
- **`GEMINI_MODEL`** (`Settings.gemini_model: str = "gemini-2.5-flash"`) - which Gemini model to call. A plain environment variable specifically so recovering from a model retirement (Google periodically retires older model versions) never requires a code change or image rebuild - see "A Note on Model Retirement" under Error Handling, below.
- **Provider selection** - there is no `AI_PROVIDER` (or similarly-named) setting. `get_ai_summary_service()` always constructs a `GeminiProvider`; which provider runs is a fact about the code (which class that one factory function instantiates), not something an operator can select at runtime today. See Extending the AI Layer for what changes if a second provider is ever added.
- **Request timeout** - `GeminiProvider.DEFAULT_TIMEOUT_MS = 30_000` (30 seconds), passed to the `google-genai` SDK's `HttpOptions`. This is a hardcoded constant in `gemini_provider.py`, **not** read from `Settings` or any environment variable - `get_ai_summary_service()` never passes a `timeout_ms` argument, so every request in every environment uses this same fixed 30-second timeout.
- **Production configuration** - no AI-specific settings differ between environments; `GEMINI_API_KEY` and `GEMINI_MODEL` are set the same way (`infra/.env`, see `docs/deployment.md`) in every environment. There is no separate "production model" or "production timeout."

---

## Error Handling

Only behavior that actually exists in the code is described here.

- **Provider failures** (network error, non-2xx from Gemini, SDK exception, missing API key) - caught inside `GeminiProvider.generate_summary`, normalized to `AIProviderError`, and logged (see Logging below). Never retried (see Validation, above).
- **Parsing/validation failures** (malformed JSON, or valid JSON that fails `ClinicalSummary`) - caught inside `AISummaryService._parse_response`, converted from `pydantic.ValidationError` to `AIProviderError("AI response failed validation")`.
- **Unavailable AI service** (no `GEMINI_API_KEY` configured) - `AIProviderError("Gemini API key is not configured")`, raised the moment a summary is actually requested (see Configuration, above).
- **At the API layer** - `app/api/routes/analyses.py` catches any exception raised during the AI call or persistence, rolls back the database session, marks the Analysis `failed` with a sanitized message (`_safe_error_message` - see Validation, above), and returns `503 Service Unavailable` with that same message as the response body. See `docs/api.md` for the exact response shape.

**Logging.** `GeminiProvider` logs one line per request: success (`ai_request_succeeded`, with `provider`, `model`, `duration_ms`) or failure (`ai_request_failed`, with the same fields plus `error_type` and a free-text `detail`). `AISummaryService` logs a validation failure (`ai_response_validation_failed`, with `provider`, `model`, and the validation error *count* only). In every case: clinical note content, prompts, raw model responses, and the detailed contents of a `ValidationError` are never logged - the `detail` field is server-side-log-only (never included in the `AIProviderError` message returned to the API layer, so it never reaches the frontend) and holds only the Gemini API's own structured description of the failure (e.g. `"RESOURCE_EXHAUSTED"`, `"models/x is not found"`), never the API key (sent via SDK header, never a URL or exception message) and never clinical text (never passed into the logging path at all). This split exists because a real incident (a retired Gemini model) was harder to diagnose than necessary when only `error_type` was logged - see Decision 20 in `docs/design-decisions.md` for the full incident and reasoning. See `docs/architecture.md`'s "Structured Logging" section for how this fits into the application's logging system as a whole (the field allowlist, request-scoped context, etc.) - not repeated here.

**Timing metrics.** `duration_ms` appears on both AI request log lines above (the time spent inside `generate_summary`, i.e. the Gemini call itself) and, separately, on the route's own `analysis_completed`/`analysis_failed` logs in `app/api/routes/analyses.py` (the whole pipeline - AI call plus persistence plus reconciliation) - the latter is a strictly broader span than the former, not a duplicate of it.

### A Note on Model Retirement

Google periodically retires older Gemini model versions, at which point every request naming that model starts failing with a `404`-shaped `APIError` (`"models/<name> is not found"`) - an upstream lifecycle event, not a bug in this application. `GEMINI_MODEL` being a plain environment variable (Configuration, above) means recovering from this never requires a code change: update the environment and restart the backend container. `gemini-2.0-flash` was retired this way in production; the application default was updated to `gemini-2.5-flash` at the same time the `detail` logging described above was added, specifically so a future retirement is diagnosable from the logs alone.

---

## Testing

AI is tested at three separate layers, each replacing a different real dependency with a fake, so the full test suite (`docs/testing.md`) never makes a live network call to Gemini:

1. **Provider level** (`tests/test_gemini_provider.py`, 14 tests) - `google.genai.Client` itself is replaced via `monkeypatch`, with small hand-written `FakeClient`/`FakeModels`/`FakeResponse` classes that record what they were called with and return a scripted response or raise a scripted error. Exercises `GeminiProvider`'s own logic: lazy client construction, the missing-key case, successful text extraction, the JSON `response_mime_type` config, and error normalization to `AIProviderError`.
2. **Service level** (`tests/test_ai_service.py`, 17 tests) - a fake in-memory `AIProvider` subclass (`FakeProvider`, defined in the test file itself) is injected directly into `AISummaryService`, one layer further removed from any SDK. Exercises prompt building, response parsing/validation (valid responses, malformed JSON, schema violations), and error propagation - with no Gemini SDK involved at all.
3. **Route level** (`tests/test_analyses.py`) - a third, route-test-local fake provider is wired in via FastAPI's own `app.dependency_overrides[get_ai_summary_service]`, so `POST /patients/{patient_id}/analyses` can be exercised end-to-end (HTTP request through to persisted Analysis) without any real AI call. One test, `test_summarize_uses_real_gemini_provider_by_default_when_key_missing`, deliberately does **not** override the dependency - it exercises the real `get_ai_summary_service()` wiring end-to-end, relying on no `GEMINI_API_KEY` being present in the test environment, and asserts the request fails gracefully as a `503` with the expected message rather than a crash.

Alongside these:

- **Prompt tests** (`tests/test_ai_prompts.py`, 6 tests) - pure string-building tests against `build_summary_prompt`: note numbering, note ordering, and that key instructions (medication identification, not resolving inconsistencies, reporting `source_note`) are present in the rendered text.
- **Reconciliation tests** (`tests/test_medication_reconciliation_service.py`, 42 tests) - the deterministic engine, tested with plain `Medication`/`MedicationMention` model instances and zero AI involvement, covering both `reconcile_ai_extracted_medications` (the live bridge from the AI flow) and `run_medication_reconciliation` (the second, currently-unwired entry point described above).
- **Normalization tests** (`tests/test_medication_normalization.py`, 19 tests) - pure-function tests for the comparison rules (whitespace/casing/alias normalization) the reconciliation engine depends on.

This layering means a change to the prompt template, the Gemini SDK integration, or the response schema each have a test layer that would catch a regression without needing any of the others to also be exercised - see `docs/testing.md` for this project's general fixture/mocking conventions (not repeated here).

---

## Extending the AI Layer

To add another provider (per README's roadmap: MedGemma, OpenBioLLM, and general provider benchmarking are listed as planned; none is implemented today - this section explains the mechanism, not a commitment to when):

1. Create a new module under `app/ai/providers/` (e.g. `medgemma_provider.py`).
2. Implement a class that subclasses `AIProvider`, sets `name` and `model`, and implements `generate_summary(prompt: str) -> str`.
3. Inside that method, catch every exception specific to that provider's own SDK and re-raise as `AIProviderError` - never let a provider-specific exception escape to the caller.
4. Update `get_ai_summary_service()` (`app/ai/service.py`) to construct the desired provider based on configuration.

No changes are needed to `AISummaryService`, `prompts.py`, `ClinicalSummary`, the API route, or the reconciliation engine - that is the entire point of the `AIProvider` interface (Decision 15). A new provider is testable immediately using the same three-layer pattern described in Testing, above: a fake at the SDK boundary, a fake `AIProvider` at the service boundary, and a `dependency_overrides` fake at the route boundary.

**What is, and isn't, an extension point today:**

- **Provider** - the intended extension point; adding one requires no change outside `app/ai/providers/` and `get_ai_summary_service()`.
- **Prompt template** - a single point of change (`SUMMARY_PROMPT_TEMPLATE`), but changing its *shape* also requires updating `ClinicalSummary`/`Medication` in lockstep, since nothing generates one from the other (a known trade-off - see Decision 16).
- **Reconciliation** - deliberately *not* an AI extension point. The comparison engine is designed to stay AI-independent (Decision 12); adding a second provider never touches `medication_reconciliation_service.py`, and that module should never gain a dependency on `AIProvider`.
- **Provider selection at runtime** - not an existing extension point. Today, adding a second provider still means only one is ever active per deployment, selected by editing `get_ai_summary_service()`, not by an environment variable a deployer can flip (see Configuration, above). Making that user-configurable would be a genuine architecture change, not something already supported.

---

## Limitations

- The AI response itself is never checked for internal consistency by the AI layer - `possible_inconsistencies` is the model's own observation, not a deterministic check. Comparison against the user's Medication list is deterministic backend logic, not part of the AI layer (see Reconciliation Pipeline, above).
- Only Gemini is implemented today. MedGemma, OpenBioLLM, and general provider benchmarking are listed on README's roadmap as planned future work, behind the same `AIProvider` interface described above - none is implemented, and this document does not describe them further than that.
- There is no retry, fallback, or evaluation system of any kind (see Validation, above) - a provider failure is a failed analysis, once, every time.
