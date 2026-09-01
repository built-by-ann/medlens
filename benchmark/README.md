# Medication Extraction Benchmark

A version-controlled, hand-written benchmark of synthetic clinical documents and their expected medication-extraction output, for evaluating MedLens's AI extraction pipeline across providers/models (GitHub issue #86).

**All data in this directory is entirely synthetic.** No case is derived from a real patient record, and none should ever be added that is. See `docs/design-decisions.md`'s Decision 8 for the project-wide synthetic-data-only policy this benchmark follows.

---

## What this is (and isn't)

This directory contains the **dataset and ground truth** (`cases/`, `loader.py`), a **runner** that executes it (`runner/`, Issue #89), a **scorer** that grades what the runner produced (`metrics/`, Issue #90), and a **report generator** that builds a human-readable, multi-provider comparison from already-scored runs (`report/`, Issue #91):

- 30 hand-written cases, each a set of one or more clinical note texts plus the medication data that should be extracted from them.
- `loader.py`, a small utility to load and structurally validate the cases.
- `runner/`, a developer CLI (`python -m benchmark.runner`) that sends each case's notes through the real MedLens prompt/provider path and records what came back. See "Running an evaluation," below.
- `metrics/`, a developer CLI (`python -m benchmark.metrics`) that scores an already-completed run: medication-detection precision/recall/F1, attribute accuracy, reliability, and latency. See "Scoring an evaluation run," below.
- `report/`, a developer CLI (`python -m benchmark.report`) that builds a human-readable comparison report (with reproducible SVG figures) from one or more already-scored runs, one provider per cited run; computes no ranking or composite score of its own. See "Generating a comparison report," below.

| Issue | Scope |
|---|---|
| #86 | The benchmark dataset and ground truth |
| #87 | OpenBioLLM provider integration |
| #88 | MedGemma provider integration |
| #89 | The evaluation runner, which executes cases against one or more providers and records structured predictions/results. Computes no quality metric. |
| #90 (this) | The evaluation metrics scorer, which grades a completed run's predictions against ground truth (medication detection, attributes, reliability, latency). Computes no ranking or report. |
| #91 | The model comparison report |

---

## Why it lives here, not under `backend/`

`benchmark/` is a top-level directory, a sibling of `backend/`, `frontend/`, `docs/`, and `infra/`, following the same reasoning `infra/` already uses for a concern that isn't part of the shipped application itself. This isn't part of the FastAPI app; it's a fixture #89's future runner and #86-#91's tooling will share, so it gets its own home rather than being nested inside `backend/app/` (the real application source) or `backend/tests/` (this project's pytest suite for the application, not a benchmark corpus).

Three pytest test files do live under `backend/tests/`: `test_benchmark_dataset.py` (validates this dataset), `test_evaluation_runner.py` (Issue #89, tests `runner/` against fakes, no network), and `test_evaluation_metrics.py` (Issue #90, tests `metrics/` against synthetic fixtures, no network). All three are picked up automatically by the existing `pytest -v`/CI run, but neither the dataset, the runner, nor the scorer is backend application code.

---

## The extraction contract this benchmark targets

Every case's `expected` output is written to match `app/ai/schemas.py`'s real, production `ClinicalSummary`/`Medication` models exactly, not an invented benchmark-specific format:

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

A **case** corresponds exactly to one call to `AISummaryService.summarize(clinical_notes: list[str])`, the real method a future evaluation runner will call. `input_notes` is that `list[str]`; `expected` is the `ClinicalSummary` that call should produce. This is also why multi-document cases don't need a separate mechanism: `source_note` (1-indexed, matching `input_notes`'s position, the same numbering `app/ai/prompts.py`'s `build_summary_prompt` already uses for "Note 1", "Note 2", ...) *is* how the real app already associates a medication with the document it came from.

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
  runner/               # Issue #89, see "Running an evaluation" below
    __main__.py
    cli.py
    providers.py
    execution.py
    models.py
    storage.py
  metrics/              # Issue #90, see "Scoring an evaluation run" below
    __main__.py
    cli.py
    matching.py
    scoring.py
    io.py
  atomic_write.py       # shared by runner/ and metrics/ (atomic JSON writes)
  results/              # gitignored, created by the runner/scorer, never committed
    <run-id>/
      manifest.json
      predictions.jsonl
      metrics.json
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
- **Attributes are preserved exactly as the source text states them and are never normalized.** A dose written "PO" stays `"PO"`, not `"oral"`; a brand name stays the brand name, not the generic. Normalization (lowercasing, the small `PO→oral`/`QD→daily` alias map) is `app/services/medication_normalization.py`'s job, a separate, later, deterministic step, not something extraction itself should do (see `docs/ai.md`'s AI/deterministic boundary).
- **`status` is never canonicalized or inferred; it is null unless the note's own words for that specific medication state one.** The production prompt (`app/ai/prompts.py`) instructs the model to "record dosage, route, frequency, and status exactly as that specific note states them... do not guess." Status gets no special treatment or canonical vocabulary anywhere in the real contract (confirmed against `app/ai/schemas.py`, which types it as a plain `str | None`, and `app/services/medication_normalization.py`, which has alias tables for route and frequency but none for status). So a note that says "stopped" gets `status: "stopped"`, never `"discontinued"`; a note that says "starting" gets `"starting"`, never `"started"`. A "Current Medications" / "Home Medications" list header, by itself, is **not** enough to set `status: "active"` for the entries under it: if no line states a status, `status` is `null`, even though the medications are clearly current in a clinical sense. This is enforced mechanically, not just by convention: `test_status_when_present_is_a_literal_substring_of_its_source_note` (`backend/tests/test_benchmark_dataset.py`) fails if any non-null `status` value isn't a literal, case-insensitive substring of the note it's attributed to.
- **`possible_inconsistencies` and `summary` are reference examples, not strict-match targets.** Both are free natural language; no two correct phrasings of the same fact are ever going to match by exact string comparison. They're included because they're part of the real `ClinicalSummary` contract (and validated against it), but a future evaluator should not grade them by exact match; see Known Limitations.
- **A case with no medications at all has `"medications": []`**, not an omitted field. This is itself the ground truth for the irrelevant-text and mentioned-but-not-a-patient-medication categories, testing that a provider doesn't over-extract.

---

## Categories represented (coverage table)

Every case is tagged with one or more of the fixed tags below (`benchmark/loader.py`'s `KNOWN_TAGS`), corresponding directly to the categories GitHub issue #86 asked this dataset to exercise. Every tag has at least two cases, enforced by `test_every_required_category_has_at_least_two_cases` in `backend/tests/test_benchmark_dataset.py`, not just documented here and left to drift.

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

This table is generated from the actual case files (`python benchmark/loader.py` prints the same breakdown), so if you add or retag a case, regenerate it rather than hand-editing the numbers above.

**Difficulty spread:** `difficulty` is a separate field (`easy`/`medium`/`hard`) from tags, so it doesn't crowd the category table above. Roughly a third of cases are `easy` (clean, unambiguous), a third `medium`, and a third `hard` (deliberately tricky: colloquial patient language with no drug name stated, a variable-dose regimen, a brand/generic pair the reconciliation engine is documented not to resolve, a multi-source negative control that must not hallucinate a medication into a note that never mentions it).

---

## Known limitations

- **30 cases is deliberately not exhaustive.** This is a hand-curated diagnostic set for catching qualitative extraction failures across real-world patterns, not a statistically powered benchmark for tight confidence intervals on a metric. See "Dataset design" reasoning in the original issue: carefully designed cases were prioritized over volume.
- **`possible_inconsistencies` and `summary` cannot be graded by exact match.** They are included for completeness against the real schema and as human-readable reference examples only. `benchmark/metrics/` (Issue #90) deliberately excludes both from automated quantitative scoring for this exact reason (see "Scoring an evaluation run," below) rather than reaching for a fuzzy/semantic/LLM-judge metric to force a number out of free text. Both remain fully available in `predictions.jsonl`/the benchmark cases for #91's qualitative discussion.
- **English-language, US-clinical-convention text only.** No non-English notes, no non-US dosing/formatting conventions.
- **No PDF or CSV input cases.** Every case here is a plain text note (matching `AISummaryService.summarize()`'s own `list[str]` input); MedLens's PDF/CSV *upload* handling (text extraction from a file) is a separate, already-tested concern (`docs/testing.md`) upstream of what this benchmark evaluates.
- **The brand/generic case (BENCH-015) intentionally represents a documented, accepted gap** (`docs/design-decisions.md` Decision 12's own stated con: "will not catch a conflict where a document uses a materially different name for the same medication"). It is not a bug in this dataset; it is here so a future evaluator's report can speak to this known limitation with real evidence instead of only a design-doc footnote.

---

## Running an evaluation

`benchmark/runner/` (Issue #89) sends every selected case's `input_notes` through the real, unmodified MedLens path, `build_summary_prompt()` (`app/ai/prompts.py`) followed by a real `AIProvider.generate_summary()`, and records what came back as structured JSON artifacts. It never builds its own prompt, never re-implements provider logic, and never compares a result against `expected`; scoring is #90's job.

```bash
# From the repository root, with the backend virtualenv active:
source backend/.venv/bin/activate
python -m benchmark.runner --providers gemini openbiollm medgemma
```

**Credentials and configuration.** `gemini` needs `GEMINI_API_KEY`, read the same way the application itself reads it. `openbiollm`/`medgemma` need no credential at all - both are served by a local Ollama daemon, configured via `OPENBIOLLM_MODEL`/`MEDGEMMA_MODEL`/`OLLAMA_BASE_URL` (falling back to each provider's own default when unset; see `docs/ai.md`). The runner never constructs `Settings` (which would require unrelated `DATABASE_URL`/`JWT_SECRET_KEY`, and only supports one active provider at a time via `AI_PROVIDER`, which is unworkable for a multi-provider run); instead it best-effort loads `backend/.env` (the same file, `override=False`, so a variable already exported into the shell always wins) and reads the relevant variables directly. A `gemini` run with no credential configured is not a hard error at startup; it fails per case as `missing_credential` (see Failure categories, below), the same way the application itself treats a missing key. An `openbiollm`/`medgemma` run with Ollama unreachable fails per case as `connection_error` instead.

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

**Output.** Each run writes `benchmark/results/<UTC timestamp>-<random suffix>/` (or `--output`'s path), gitignored and never committed, even though every note in this dataset is synthetic; a raw model response hasn't been reviewed as safe to publish and there's no reason to risk it. Two files:

- **`manifest.json`:** one object, written at the *start* of the run (`status: "running"`, `completed_at: null`) and rewritten at the end (`status: "complete"` or `"interrupted"`, real `completed_at`/`result_count`). A manifest still reading `"running"` on disk means the process crashed before finishing. This is not distinguished from a genuinely stuck run, deliberately: recovering further than "this run didn't finish" isn't worth the complexity. Records: `run_id`, `started_at`/`completed_at`, `status`, `benchmark_fingerprint` (a sha256 of every loaded case's canonical content, stable across file reformatting, changes if any case's actual content changes), `case_count`, `selected_providers`, `case_filter`/`tag_filter` (as passed on the command line, `null` if unset), each provider's `model`/`inference_backend`/`generation_params`/`runtime_version` (the installed Ollama server version for `openbiollm`/`medgemma`, best-effort via `GET /api/version`, `null` if unreachable at manifest-build time or not applicable, e.g. `gemini`), `git_commit`/`git_dirty` (best-effort, `null` outside a git checkout), `python_version`, `predictions_file`, `result_count`.
- **`predictions.jsonl`:** one JSON object per line, one line per attempted `(case, provider)` pair, appended (and flushed) as the run progresses so a killed process still leaves a readable partial file. Each record's `provider_response` is **the exact string `AIProvider.generate_summary()` returned, before any evaluation-framework parsing or validation**, and this is not the same thing for every provider: it's Gemini's genuinely raw output, but OpenBioLLM's/MedGemma's already syntactically-cleaned output (markdown fences and surrounding prose stripped inside the provider itself, see `docs/ai.md`'s Provider Abstraction section), since that cleanup is invisible outside `generate_summary()`. `parsed_clinical_summary` is present only when parsing fully succeeds; otherwise it's `null` and `parsing.error_category` says why.

**Parsing.** Every response is parsed in two explicit stages, `json.loads()` then `ClinicalSummary.model_validate()` (the real, unmodified schema), rather than the one-line form `AISummaryService._parse_response` uses in production, specifically so "invalid JSON" and "valid JSON, wrong shape" can be told apart as separate categories. Neither stage repairs, cleans, or otherwise modifies `provider_response`.

**Failure categories** (`parsing.error_category`), derived from each provider's own existing exception boundaries, not invented for this framework:

| Category | Meaning |
|---|---|
| `missing_credential` | The relevant API key isn't configured (`gemini` only). |
| `connection_error` | Ollama wasn't reachable at the configured `OLLAMA_BASE_URL` (`openbiollm`/`medgemma` only). |
| `model_not_found` | The named Ollama model isn't installed locally (`openbiollm`/`medgemma` only). |
| `empty_response` | The provider returned nothing usable. |
| `timeout` | The provider (or the local Ollama request) timed out. |
| `provider_error` | A provider-SDK-level error/HTTP failure. |
| `unexpected_error` | Anything else escaping a provider's own error wrapping, a defensive catch-all. |
| `invalid_json` | The response wasn't valid JSON at all. |
| `schema_validation_error` | Valid JSON that doesn't match `ClinicalSummary`. |

A single `(case, provider)` failure never stops the run; every remaining case/provider pair is still attempted. **Known asymmetry:** `GeminiProvider` has no SDK exception distinct from a generic error for a network timeout (only `genai_errors.APIError` is caught specifically in `gemini_provider.py`), so a Gemini timeout currently classifies as `unexpected_error`, not `timeout`, unlike OpenBioLLM/MedGemma, which raise a distinguishable `TimeoutError`/`urllib.error.URLError`. This is a real, pre-existing difference between the provider implementations, documented here rather than fixed by modifying `GeminiProvider` as part of this issue.

**Reproducibility.** The identical-prompt guarantee: `build_summary_prompt(case.input_notes)` is called exactly once per case, and that exact string (never rebuilt) is sent to every selected provider for that case; each prediction records a `prompt_hash` (sha256) proving it. Combined with the manifest's `benchmark_fingerprint`, `git_commit`, and each provider's `model`/`inference_backend`/`generation_params`/`runtime_version`, the metrics scorer (#90, below) and any later comparison (#91) can tell precisely what dataset state, code state, and configuration a given run reflects.

---

## Scoring an evaluation run

`benchmark/metrics/` (Issue #90) grades an already-completed `benchmark/runner` run against the benchmark's own ground truth: medication-detection precision/recall/F1, attribute accuracy, source-attribution accuracy, reliability, and latency. It never calls a provider and never reruns anything; it only reads `manifest.json`/`predictions.jsonl` and the current `benchmark/cases/*.json`.

```bash
# From the repository root, with the backend virtualenv active:
source backend/.venv/bin/activate
python -m benchmark.metrics benchmark/results/<run-id>
```

Writes `metrics.json` into that same run directory.

### Medication matching

Before any field is scored, a predicted medication must be paired with an expected one. **Identity is normalized medication name alone:** Unicode NFC, strip, collapse internal whitespace, casefold (no punctuation stripping, no semantic aliasing: `"PO"`/`"oral"`, `"BID"`/`"twice daily"`, `"10mg"`/`"10 mg"`, and `"stopped"`/`"discontinued"` are all treated as different strings, on purpose; see "Attribute comparison," below).

For a name appearing exactly once on both sides, the pair is immediate. For a **duplicate-name group** (more than one predicted or expected medication sharing a name within one case; 9 of the 30 real cases have at least one), the one-to-one assignment that maximizes normalized agreement on **dosage, route, and frequency only** is chosen, via an exhaustive search over every possible pairing (never a greedy walk, since the largest group in this benchmark is 3 items, so this is cheap). `source_note`, `status`, and `notes` are never used to decide who matches whom:

- **`source_note`** is itself an independently scored field (source-attribution accuracy, below); using it to *establish* a match would make its own accuracy close to 100% by construction, a circular metric.
- **`status`** is sparse (26.9% non-null across the benchmark) and free-form; it's scored on its own merits, not used to help find its own pairing.
- **`notes`** is free text, never exact-match scored at all (see below).

**A real, checked limitation.** Before implementing this, every duplicate-name group in the actual 30 cases was audited by hand. Six groups (BENCH-006 and BENCH-022's `atorvastatin` duplicates, BENCH-010's `metformin` [three-way] and `lisinopril` duplicates, and BENCH-029's `lisinopril` and `furosemide` duplicates) have **identical (or entirely null) dosage/route/frequency across every member**, so no permitted signal can tell them apart at all; the only field that differs between them is `source_note` (or, for the two `atorvastatin` groups, `status`). For these specific groups, a pairing is still produced deterministically (so the run scores identically every time), but which specific expected item a given predicted item lands on is not actually determined by any permitted signal, so those particular matched pairs are excluded from `source_note` accuracy's denominator entirely (`excluded_ambiguous_pairs`, below) rather than scored right or wrong by what would amount to a coin flip. Every other score (dosage/route/frequency/notes/detection) is completely unaffected, since a tie by definition means those fields already agree identically no matter which assignment is chosen.

### Attribute comparison

`dosage`, `route`, `frequency`, `status`: **normalized-exact only** (the same normalization as matching, above), with no semantic/alias normalization. This is deliberate, not an oversight: the ground truth itself preserves source wording exactly (see "How ground truth is defined," above), so scoring against a more lenient, meaning-aware contract than the one models were actually asked to follow would hide real extraction-fidelity signal. For each field:

- `accuracy`: correct / matched pairs (both-null counts as correct).
- `accuracy_given_expected_non_null`: correct / (pairs where expected is non-null); "when there was something to extract, how often was it right."
- `hallucination_rate_given_expected_null`: (predicted non-null when expected null) / (pairs where expected is null); "how often was something invented where there was nothing to find."

This split matters because `status` is null 73% of the time in this benchmark, so plain `accuracy` alone would let a model that predicts `status: null` for everything score ~73% while never once correctly extracting a real status; `accuracy_given_expected_non_null` is the number that actually measures that. `matched_pairs == 0` reports `0.0` for every rate, not `1.0`, because "no data" is not the same claim as "perfect," and the accompanying count always disambiguates the two.

`notes` is free text and is **never exact-match or fuzzy-scored**, only presence agreement, over matched pairs: `both_null`, `both_non_null` (regardless of exact wording), `under_annotated` (expected non-null, predicted null), `over_annotated` (expected null, predicted non-null: a hallucinated annotation).

`source_note`: ordinary source-attribution accuracy over matched pairs, computed strictly *after* matching (never part of it, see above). Expected `source_note` is always non-null in this benchmark; a predicted `null` counts as incorrect, never excused. `excluded_ambiguous_pairs` is the count of matched pairs whose specific pairing wasn't determined by a permitted signal (see the duplicate-group limitation above); `accuracy`'s denominator is `scoreable_pairs`, not `matched_pairs`.

### Medication detection

`TP` = matched pair, `FP` = unmatched predicted, `FN` = unmatched expected. **Zero-denominator convention:** precision is `1.0` when nothing was predicted (vacuously precise), recall is `1.0` when nothing was expected (vacuously complete; six real cases in this benchmark have zero expected medications), and F1 is `1.0` only when both are (whether genuinely or vacuously); a real over- or under-extraction still drives F1 to `0.0`.

Computed two ways, both reported:

- **`end_to_end` (primary):** every attempted case. A case whose output wasn't schema-valid contributes an empty predicted-medications list (never inferred or recovered from `provider_response`); its full set of expected medications becomes FN. This is the number that reflects real-world usefulness: a model that "wins" by silently failing scores worse, not the same.
- **`conditional_on_valid_output` (secondary, diagnostic):** schema-valid cases only, answering "given we could score it, how good was the extraction." Always reported next to `evaluable_case_count` and reliability's `evaluable_case_rate` (below); never quoted alone, since a high conditional F1 over a small evaluable fraction would misrepresent overall quality.

**Known interaction, by design:** a case with zero expected medications where the provider call *itself* failed still scores a vacuous "perfect" `end_to_end` F1 for that one case (nothing was expected, so nothing could be missed). Medication F1 alone does not fully capture reliability, which is exactly why reliability metrics (below) are always reported alongside it, never folded into it.

Each interpretation reports both **micro** (aggregate TP/FP/FN across every medication object first, then compute one P/R/F1; the primary/headline number, weighting every real medication equally) and **macro** (compute P/R/F1 per case, then average the per-case scores unweighted, giving equal weight per case regardless of medication count).

### Reliability

Four rates, four different denominators, never merged into one composite and never folded into medication F1 beyond `end_to_end`'s explicit failed-case treatment above:

| Metric | Denominator |
|---|---|
| `provider_call_success_rate` | every attempted `(case, provider)` pair |
| `json_validity_rate` | pairs where the provider call succeeded at all |
| `schema_validity_rate` | pairs where the JSON was valid at all |
| `evaluable_case_rate` | every attempted pair (unconditional); always read alongside `conditional_on_valid_output` |

### Latency

`count`/`mean`/`median`/`p95` (nearest-rank)/`min`/`max`, computed **only over `provider_call_succeeded == true`**, because a failed call's near-instant latency isn't a measure of model speed and would distort every statistic. With at most 30 samples per provider, this is not production-grade latency benchmarking; `count` is always reported alongside so a reader can see exactly how few samples back these numbers.

### Grouped metrics

`by_difficulty` and `by_tag` report the same `{n, micro, macro}` shape (`end_to_end` interpretation only, to stay compact) per group. A case can appear under more than one tag (matching the dataset's own multi-tag design), so tag `n` values don't sum to the total case count. Small groups (some tags have as few as 2 cases, the enforced minimum) are never suppressed, but `n` is always present precisely so a group's numbers are never read as more statistically meaningful than they are. Whether a group is *reliable enough* to draw a conclusion from is #91's judgment to make, not this scorer's.

### Invalid/incomplete runs

Fail-loud by default, because scoring through an integrity problem would make the resulting numbers scientifically misleading:

| Condition | Default | Override |
|---|---|---|
| `manifest.status != "complete"` | refuse | `--allow-incomplete` |
| Recomputed benchmark fingerprint ≠ the run's recorded one | refuse | `--allow-fingerprint-mismatch` |
| Duplicate `(case_id, provider)` record | refuse | none; always a data-integrity bug |
| Unknown `case_id` in `predictions.jsonl` | refuse | none |
| A selected provider has zero prediction records | refuse | none |
| `metrics.json` already exists | refuse | `--force` |

Any override actually used is recorded in `metrics.json`'s own `overrides`/`partial`/`fingerprint_mismatch` fields, never silently.

---

## Generating a comparison report (Issue #91)

See `docs/model-evaluation.md` for the evaluation methodology this report presents results under (dataset, providers, protocol, metric definitions, limitations); this section only documents the report-generation tool's own mechanics.

`benchmark/report/` builds a human-readable, multi-provider comparison report from one or more **already-scored** run directories (each must already have a `metrics.json`; run `python -m benchmark.metrics <run_dir>` first). It never calls an AIProvider, never reruns anything, and never recomputes a #90 metric; it only reads and presents what #89/#90 already wrote.

Each provider is cited from its own source run, which is exactly what makes it possible to build one report from, e.g., a clean Gemini-only run plus a separate run where Gemini's own calls happened to be affected by an unrelated account issue. Only OpenBioLLM/MedGemma's records from that second run are ever read:

```bash
# From the repository root, with the backend virtualenv active:
python -m benchmark.report \
  --provider gemini=<run-id-a> \
  --provider openbiollm=<run-id-b> \
  --provider medgemma=<run-id-b> \
  --output benchmark/report/output/<a-name-for-this-report>
```

**Comparability validation**, before anything is rendered (fail-loud, no override flag: a report built across incomparable runs would be scientifically misleading in a way no flag should paper over):

| Check | Failure mode |
|---|---|
| Every cited run has `manifest.json` and `metrics.json` | refuse, names the missing file |
| Every cited provider was actually selected/scored in its run | refuse |
| `benchmark_fingerprint` identical across every cited run | refuse, since the runs measured different dataset states |
| Every cited run covers the same set of case ids | refuse, since a partial run was mixed with a full one |
| Per-case `prompt_hash` identical for every case shared across cited runs | refuse, since the literal prompt differed |
| `git_commit` identical across cited runs | **warning only**, surfaced in the report's own Provenance section |

**Report contents**: provenance (which run supplied each provider, its exact model/backend/generation params); reliability (a compact heatmap, providers by rate, so a provider with 100% call success but 0% structured-output validity is immediately visible, with each column's own denominator labeled directly on the chart rather than implying one shared, sequential base); medication detection (a horizontal dot plot; end-to-end always shown; `conditional_on_valid_output`/attribute tables shown only for a provider with at least one evaluable case, since a provider with zero is marked "not applicable" and never rendered as a misleading 0%); difficulty breakdown (a horizontal dot plot) and tag breakdown (a horizontal dumbbell plot comparing evaluable providers directly, all 18 tags shown, with a zero-evaluable provider omitted from the chart entirely behind one explanatory annotation rather than 18 individually meaningless marks); latency (explicitly labeled API vs. local, not hardware-comparable, with that caveat kept in this prose rather than inside the figure itself); a qualitative section on `possible_inconsistencies`/`summary` (the two `ClinicalSummary` fields #90 deliberately never scores, presented as descriptive output behavior only, never as an accuracy/recall/quality claim, since no ground truth exists for either); and a dedicated Limitations section. See `benchmark/report/render.py` for the exact section order.

**Figure generation**: every figure is a Matplotlib chart (`benchmark/report/charts.py`), rendered directly to SVG from `metrics.json` on each run; there is no manually edited SVG anywhere, and regenerating a report from the same source runs always reproduces the same figures. `benchmark/report/chart_data.py` holds the pure "what to plot" logic (row order, which values are "not applicable", tag-label humanization), entirely independent of Matplotlib, and `benchmark/report/chart_style.py` holds the one shared palette/typography/color-assignment module every chart draws from, so the same provider is always the same color across all five figures in one report. No interactive charting library and no headless-browser renderer (e.g. Plotly/Kaleido) is used or needed: Matplotlib's own `savefig(..., format="svg")` needs no external binary, keeping figure generation as reproducible and dependency-light as the rest of this tooling.

**Output location and promotion**: `--output` writes `report.md` + `figures/*.svg` into a working directory (by convention, `benchmark/report/output/`, gitignored, for the same reason as `benchmark/results/`: the qualitative section quotes raw model text that hasn't been reviewed yet). A specific, reviewed report is promoted into the repository **manually, deliberately, never automatically**:

1. Generate and read `report.md` yourself; check the qualitative excerpts and the OpenBioLLM/zero-evaluable notes in particular.
2. Copy the reviewed `report.md` to `docs/model-comparison-report.md`, and `figures/*.svg` to `docs/assets/evaluation/`.
3. In the copied file, change every `figures/` image path to `assets/evaluation/` (the only change promotion requires, since `docs/model-comparison-report.md` and `docs/assets/evaluation/` are siblings, the same way `report.md` and its own `figures/` are siblings in the working output). `docs/model-comparison-report.md` holds only the promoted results, never the methodology; see `docs/model-evaluation.md` for that.

---

## Running the validation

```bash
cd backend
source .venv/bin/activate
pytest tests/test_benchmark_dataset.py tests/test_evaluation_runner.py tests/test_evaluation_metrics.py -v
```

or, to see the coverage breakdown directly:

```bash
python benchmark/loader.py
```

All three check structure/schema compatibility and runner/scorer behavior using fakes and synthetic fixtures only; none call a real AI provider or the network. Only `python -m benchmark.runner` itself makes real provider calls.
