# Medication Extraction Benchmark

A version-controlled, hand-written benchmark of synthetic clinical documents and their expected medication-extraction output, for evaluating MedLens's AI extraction pipeline across providers/models (GitHub issue #86).

**All data in this directory is entirely synthetic.** No case is derived from a real patient record, and none should ever be added that is. See `docs/design-decisions.md`'s Decision 8 for the project-wide synthetic-data-only policy this benchmark follows.

---

## What this is (and isn't)

This is a **dataset and ground truth only**. It contains:

- 30 hand-written cases, each a set of one or more clinical note texts plus the medication data that should be extracted from them.
- `loader.py`, a small utility to load and structurally validate the cases.
- Nothing else. There is no code here that calls an AI provider, runs an extraction, or computes a score.

Running the benchmark against a real provider, scoring the results (precision/recall/F1, etc.), and producing a comparison report are separate, future pieces of work:

| Issue | Scope |
|---|---|
| #86 (this) | The benchmark dataset and ground truth |
| #87 | OpenBioLLM provider integration |
| #88 | MedGemma provider integration |
| #89 | The evaluation framework (a runner that executes cases against a provider) |
| #90 | Evaluation metrics (precision/recall/F1, etc.) |
| #91 | The model comparison report |

---

## Why it lives here, not under `backend/`

`benchmark/` is a top-level directory, a sibling of `backend/`, `frontend/`, `docs/`, and `infra/` - the same reasoning `infra/` already uses for a concern that isn't part of the shipped application itself. This isn't part of the FastAPI app; it's a fixture #89's future runner and #86-#91's tooling will share, so it gets its own home rather than being nested inside `backend/app/` (the real application source) or `backend/tests/` (this project's pytest suite for the application, not a benchmark corpus).

One pytest test file does live under `backend/tests/` (`test_benchmark_dataset.py`) - it validates this dataset and is picked up automatically by the existing `pytest -v`/CI run, but the dataset itself is not backend application code.

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

## How future evaluation code (#89) should consume this

```python
from benchmark.loader import load_cases

for case in load_cases():
    # case.input_notes -> feed directly to AISummaryService.summarize()
    # case.expected["medications"] -> the primary, field-by-field gradable ground truth
    # case.expected["possible_inconsistencies"] / ["summary"] -> reference only, not exact-match graded
    # case.tags / case.difficulty -> for breaking down results by category
    ...
```

`load_cases()` already validates every case (including against the real `ClinicalSummary` model) and raises `BenchmarkValidationError` on anything malformed, so #89's runner does not need to re-implement that check - only import it.

---

## Running the validation

```bash
cd backend
source .venv/bin/activate
pytest tests/test_benchmark_dataset.py -v
```

or, to see the coverage breakdown directly:

```bash
python benchmark/loader.py
```

Both check structure and schema compatibility only - neither calls an AI provider or the network.
