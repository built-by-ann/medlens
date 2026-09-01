# Medication Extraction Benchmark

A version-controlled, hand-written benchmark of synthetic clinical documents and their expected medication-extraction output, for evaluating MedLens's AI extraction pipeline across providers/models (GitHub issue #86).

**All data in this directory is entirely synthetic.** No case is derived from a real patient record, and none should ever be added that is. See `docs/design-decisions.md`'s Decision 8 for the project-wide synthetic-data-only policy this benchmark follows.

---

## What this is (and isn't)

This directory contains the **dataset and ground truth** (`cases/`, `loader.py`) plus a **runner** that executes it (`runner/`, Issue #89):

- 30 hand-written cases, each a set of one or more clinical note texts plus the medication data that should be extracted from them.
- `loader.py`, a small utility to load and structurally validate the cases.
- `runner/`, a developer CLI (`python -m benchmark.runner`) that sends each case's notes through the real MedLens prompt/provider path and records what came back - see "Running an evaluation," below.
- Nothing that computes a score. The runner records raw/parsed predictions and failures; it does not compare them against `expected`, compute precision/recall/F1, or rank providers - that is #90/#91's work.

Scoring the results (precision/recall/F1, etc.) and producing a comparison report are separate, future pieces of work - see `benchmark/runner/` (Issue #89, documented below) for the part of this that does exist today: running the dataset against a real provider and recording what happened.

| Issue | Scope |
|---|---|
| #86 | The benchmark dataset and ground truth |
| #87 | OpenBioLLM provider integration |
| #88 | MedGemma provider integration |
| #89 (this) | The evaluation runner - executes cases against one or more providers and records structured predictions/results. Computes no quality metric. |
| #90 | Evaluation metrics (precision/recall/F1, etc.) |
| #91 | The model comparison report |

---

## Why it lives here, not under `backend/`

`benchmark/` is a top-level directory, a sibling of `backend/`, `frontend/`, `docs/`, and `infra/` - the same reasoning `infra/` already uses for a concern that isn't part of the shipped application itself. This isn't part of the FastAPI app; it's a fixture #89's future runner and #86-#91's tooling will share, so it gets its own home rather than being nested inside `backend/app/` (the real application source) or `backend/tests/` (this project's pytest suite for the application, not a benchmark corpus).

Two pytest test files do live under `backend/tests/` - `test_benchmark_dataset.py` (validates this dataset) and `test_evaluation_runner.py` (Issue #89, tests `runner/` against fakes, no network) - both picked up automatically by the existing `pytest -v`/CI run, but neither the dataset nor the runner is backend application code.

---

## The extraction contract this benchmark targets

Every case's `expected` output is written to match `app/ai/schemas.py`'s real, production `ClinicalSummary`/`Medication` models exactly - not an invented benchmark-specific format:

```python
class Medication(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    dosage: str | None = None
    route: str | None = None
    frequency: str | None = None
    status: str | None = None
    notes: str | None = None
    source_note: int | None = None   # 1-indexed position in input_notes

class ClinicalSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    medications: list[Medication]
    possible_inconsistencies: list[str]
    summary: str
```

A **case** corresponds exactly to one call to `AISummaryService.summarize(clinical_notes: list[str])` - the real method a future evaluation runner will call. `input_notes` is that `list[str]`; `expected` is the `ClinicalSummary` that call should produce. This is also why multi-document cases don't need a separate mechanism: `source_note` (1-indexed, matching `input_notes`'s position, the same numbering `app/ai/prompts.py`'s `build_summary_prompt` already uses for "Note 1", "Note 2", ...) *is* how the real app already associates a medication with the document it came from.

---

## File format

```
benchmark/
  README.md
  loader.py
  cases/
    BENCH-001.json
    BENCH-002.json
    ...
  runner/               # Issue #89 - see "Running an evaluation" below
    __main__.py
    cli.py
    providers.py
    execution.py
    models.py
    storage.py
  results/              # gitignored - created by the runner, never committed
    <run-id>/
      manifest.json
      predictions.jsonl
```

One case per file, `case_id` matching the filename. Each file:

```json
{
  "case_id": "BENCH-006",
  "tags": ["multi_document", "dose_change", "conflicting_across_documents", "reconciliation_relevant"],
  "difficulty": "medium",
  "description": "A recent visit documents a dose increase; a home medication list on file hasn't caught up.",
  "input_notes": [
    "Cardiology follow-up: ... Amlodipine increased to 10 mg oral once daily, up from the previous 5 mg dose. ...",
    "Home Medication List (on file, last updated 2 months ago): Amlodipine 5 mg oral once daily. ..."
  ],
  "expected": {
    "medications": [
      {"name": "Amlodipine", "dosage": "10 mg", "route": "oral", "frequency": "once daily", "status": null, "notes": "increased from 5 mg", "source_note": 1},
      {"name": "Amlodipine", "dosage": "5 mg", "route": "oral", "frequency": "once daily", "status": null, "notes": null, "source_note": 2}
    ],
    "possible_inconsistencies": ["Amlodipine dose differs between the cardiology note (10 mg) and the home medication list (5 mg)."],
    "summary": "..."
  }
}
```

`input_notes` (the source clinical text) and `expected` (the ground truth) are separate top-level keys, never blended together, so a future runner can feed `input_notes` straight into `AISummaryService.summarize()` and diff the result against `expected` with no text-scraping in between.

---

## How ground truth is defined

- **`expected.medications` is the primary, strictly-gradable ground truth.** Every field is checkable directly against a real extraction's output, field by field.
- **Attributes are preserved exactly as the source text states them - never normalized.** A dose written "PO" stays `"PO"`, not `"oral"`; a brand name stays the brand name, not the generic. Normalization (lowercasing, the small `PO→oral`/`QD→daily` alias map) is `app/services/medication_normalization.py`'s job, a separate, later, deterministic step - not something extraction itself should do (see `docs/ai.md`'s AI/deterministic boundary).
- **`status` is never canonicalized or inferred - it is null unless the note's own words for that specific medication state one.** The production prompt (`app/ai/prompts.py`) instructs the model to "record dosage, route, frequency, and status exactly as that specific note states them... do not guess" - status gets no special treatment or canonical vocabulary anywhere in the real contract (confirmed against `app/ai/schemas.py`, which types it as a plain `str | None`, and `app/services/medication_normalization.py`, which has alias tables for route and frequency but none for status). So a note that says "stopped" gets `status: "stopped"`, never `"discontinued"`; a note that says "starting" gets `"starting"`, never `"started"`. A "Current Medications" / "Home Medications" list header, by itself, is **not** enough to set `status: "active"` for the entries under it - if no line states a status, `status` is `null`, even though the medications are clearly current in a clinical sense. This is enforced mechanically, not just by convention: `test_status_when_present_is_a_literal_substring_of_its_source_note` (`backend/tests/test_benchmark_dataset.py`) fails if any non-null `status` value isn't a literal, case-insensitive substring of the note it's attributed to.
- **`possible_inconsistencies` and `summary` are reference examples, not strict-match targets.** Both are free natural language; no two correct phrasings of the same fact are ever going to match by exact string comparison. They're included because they're part of the real `ClinicalSummary` contract (and validated against it), but a future evaluator should not grade them by exact match - see Known Limitations.
- **A case with no medications at all has `"medications": []`**, not an omitted field - this is itself the ground truth for the irrelevant-text and mentioned-but-not-a-patient-medication categories, testing that a provider doesn't over-extract.

---

## Categories represented (coverage table)

Every case is tagged with one or more of the fixed tags below (`benchmark/loader.py`'s `KNOWN_TAGS`), corresponding directly to the categories GitHub issue #86 asked this dataset to exercise. Every tag has at least two cases - enforced by `test_every_required_category_has_at_least_two_cases` in `backend/tests/test_benchmark_dataset.py`, not just documented here and left to drift.

| Tag | Count | Case IDs |
|---|---|---|
| `straightforward_list` | 8 | BENCH-001, 002, 010, 012, 013, 016, 024, 029 |
| `narrative_text` | 7 | BENCH-003, 004, 005, 014, 025, 028, 030 |
| `active_medication` | 2 | BENCH-003, 007 |
| `discontinued` | 2 | BENCH-004, 023 |
| `newly_started` | 3 | BENCH-005, 022, 028 |
| `dose_change` | 2 | BENCH-006, 022 |
| `status_change` | 3 | BENCH-007, 023, 028 |
| `multi_document` | 10 | BENCH-006, 007, 008, 009, 010, 015, 022, 023, 026, 029 |
| `conflicting_across_documents` | 4 | BENCH-006, 007, 009, 026 |
| `missing_fields` | 4 | BENCH-001, 002, 025, 029 |
| `prn` | 4 | BENCH-002, 011, 024, 027 |
| `route_variety` | 4 | BENCH-008, 011, 012, 027 |
| `frequency_variety` | 3 | BENCH-009, 013, 026 |
| `brand_vs_generic` | 2 | BENCH-014, 015 |
| `abbreviation` | 3 | BENCH-011, 016, 027 |
| `irrelevant_text` | 3 | BENCH-017, 018, 030 |
| `mentioned_not_active` | 4 | BENCH-019, 020, 021, 030 |
| `reconciliation_relevant` | 9 | BENCH-006, 007, 008, 010, 015, 022, 023, 026, 029 |

This table is generated from the actual case files (`python benchmark/loader.py` prints the same breakdown) - if you add or retag a case, regenerate it rather than hand-editing the numbers above.

**Difficulty spread:** `difficulty` is a separate field (`easy`/`medium`/`hard`) from tags, so it doesn't crowd the category table above. Roughly a third of cases are `easy` (clean, unambiguous), a third `medium`, and a third `hard` (deliberately tricky: colloquial patient language with no drug name stated, a variable-dose regimen, a brand/generic pair the reconciliation engine is documented not to resolve, a multi-source negative control that must not hallucinate a medication into a note that never mentions it).

---

## Known limitations

- **30 cases is deliberately not exhaustive.** This is a hand-curated diagnostic set for catching qualitative extraction failures across real-world patterns, not a statistically powered benchmark for tight confidence intervals on a metric. See "Dataset design" reasoning in the original issue: carefully designed cases were prioritized over volume.
- **`possible_inconsistencies` and `summary` cannot be graded by exact match.** They are included for completeness against the real schema and as human-readable reference examples only.
- **English-language, US-clinical-convention text only.** No non-English notes, no non-US dosing/formatting conventions.
- **No PDF or CSV input cases.** Every case here is a plain text note (matching `AISummaryService.summarize()`'s own `list[str]` input) - MedLens's PDF/CSV *upload* handling (text extraction from a file) is a separate, already-tested concern (`docs/testing.md`) upstream of what this benchmark evaluates.
- **The brand/generic case (BENCH-015) intentionally represents a documented, accepted gap** (`docs/design-decisions.md` Decision 12's own stated con: "will not catch a conflict where a document uses a materially different name for the same medication"). It is not a bug in this dataset - it is here so a future evaluator's report can speak to this known limitation with real evidence instead of only a design-doc footnote.

---

## Running an evaluation

`benchmark/runner/` (Issue #89) sends every selected case's `input_notes` through the real, unmodified MedLens path - `build_summary_prompt()` (`app/ai/prompts.py`), then a real `AIProvider.generate_summary()` - and records what came back as structured JSON artifacts. It never builds its own prompt, never re-implements provider logic, and never compares a result against `expected`; scoring is #90's job.

```bash
# From the repository root, with the backend virtualenv active:
source backend/.venv/bin/activate
python -m benchmark.runner --providers gemini openbiollm medgemma
```

**Credentials.** The runner needs the same environment variables the application itself uses - `GEMINI_API_KEY` for `gemini`, `HUGGINGFACE_API_KEY` for `openbiollm`/`medgemma` (shared, exactly as in `docs/ai.md`). It never constructs `Settings` (which would require unrelated `DATABASE_URL`/`JWT_SECRET_KEY`, and only supports one active provider at a time via `AI_PROVIDER` - unworkable for a multi-provider run); instead it best-effort loads `backend/.env` (the same file, `override=False`, so a credential already exported into the shell always wins) and reads the two keys directly. A provider run with no credential configured is not a hard error at startup - it fails per case as `missing_credential` (see Failure categories, below), the same way the application itself treats a missing key.

**Selecting providers/cases:**

```bash
# Only one provider
python -m benchmark.runner --providers medgemma

# Only specific cases
python -m benchmark.runner --cases BENCH-006 BENCH-007

# Only cases carrying a given tag
python -m benchmark.runner --tags multi_document

# --cases and --tags intersect when both are given: only cases matching BOTH
python -m benchmark.runner --cases BENCH-006 BENCH-007 --tags multi_document

# A custom output location (must not already exist)
python -m benchmark.runner --output benchmark/results/my-run
```

Filtering to a combination that matches no cases fails clearly (a printed error, exit code 1, no output directory created) rather than silently writing an empty run.

**Output.** Each run writes `benchmark/results/<UTC timestamp>-<random suffix>/` (or `--output`'s path), gitignored - never committed, even though every note in this dataset is synthetic; a raw model response hasn't been reviewed as safe to publish and there's no reason to risk it. Two files:

- **`manifest.json`** - one object, written at the *start* of the run (`status: "running"`, `completed_at: null`) and rewritten at the end (`status: "complete"` or `"interrupted"`, real `completed_at`/`result_count`). A manifest still reading `"running"` on disk means the process crashed before finishing - not distinguished from a genuinely stuck run, deliberately: recovering further than "this run didn't finish" isn't worth the complexity. Records: `run_id`, `started_at`/`completed_at`, `status`, `benchmark_fingerprint` (a sha256 of every loaded case's canonical content - stable across file reformatting, changes if any case's actual content changes), `case_count`, `selected_providers`, `case_filter`/`tag_filter` (as passed on the command line, `null` if unset), each provider's `model`/`inference_backend`/`generation_params`, `git_commit`/`git_dirty` (best-effort, `null` outside a git checkout), `python_version`, `predictions_file`, `result_count`.
- **`predictions.jsonl`** - one JSON object per line, one line per attempted `(case, provider)` pair, appended (and flushed) as the run progresses so a killed process still leaves a readable partial file. Each record's `provider_response` is **the exact string `AIProvider.generate_summary()` returned, before any evaluation-framework parsing or validation** - this is not the same thing for every provider: it's Gemini's genuinely raw output, but OpenBioLLM's/MedGemma's already syntactically-cleaned output (markdown fences and surrounding prose stripped inside the provider itself - see `docs/ai.md`'s Provider Abstraction section), since that cleanup is invisible outside `generate_summary()`. `parsed_clinical_summary` is present only when parsing fully succeeds; otherwise it's `null` and `parsing.error_category` says why.

**Parsing.** Every response is parsed in two explicit stages - `json.loads()`, then `ClinicalSummary.model_validate()` (the real, unmodified schema) - rather than the one-line form `AISummaryService._parse_response` uses in production, specifically so "invalid JSON" and "valid JSON, wrong shape" can be told apart as separate categories. Neither stage repairs, cleans, or otherwise modifies `provider_response`.

**Failure categories** (`parsing.error_category`), derived from each provider's own existing exception boundaries, not invented for this framework:

| Category | Meaning |
|---|---|
| `missing_credential` | The relevant API key isn't configured. |
| `empty_response` | The provider returned nothing usable. |
| `timeout` | The provider's own SDK reported a timeout (`InferenceTimeoutError`, for OpenBioLLM/MedGemma). |
| `provider_error` | A provider-SDK-level error/HTTP failure. |
| `unexpected_error` | Anything else escaping a provider's own error wrapping - a defensive catch-all. |
| `invalid_json` | The response wasn't valid JSON at all. |
| `schema_validation_error` | Valid JSON that doesn't match `ClinicalSummary`. |

A single `(case, provider)` failure never stops the run - every remaining case/provider pair is still attempted. **Known asymmetry:** `GeminiProvider` has no SDK exception distinct from a generic error for a network timeout (only `genai_errors.APIError` is caught specifically in `gemini_provider.py`), so a Gemini timeout currently classifies as `unexpected_error`, not `timeout`, unlike OpenBioLLM/MedGemma. This is a real, pre-existing difference between the provider implementations, documented here rather than fixed by modifying `GeminiProvider` as part of this issue.

**Reproducibility.** The identical-prompt guarantee: `build_summary_prompt(case.input_notes)` is called exactly once per case, and that exact string (never rebuilt) is sent to every selected provider for that case - each prediction records a `prompt_hash` (sha256) proving it. Combined with the manifest's `benchmark_fingerprint`, `git_commit`, and each provider's `model`/`generation_params`, a later comparison (#90/#91) can tell precisely what dataset state, code state, and configuration a given run reflects.

---

## Running the validation

```bash
cd backend
source .venv/bin/activate
pytest tests/test_benchmark_dataset.py tests/test_evaluation_runner.py -v
```

or, to see the coverage breakdown directly:

```bash
python benchmark/loader.py
```

All three check structure/schema compatibility and runner behavior using fakes only - none call a real AI provider or the network. Only `python -m benchmark.runner` itself makes real provider calls.
