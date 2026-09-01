"""Loading and structural validation for the synthetic extraction benchmark
(GitHub issue #86).

This module is deliberately narrow: it reads benchmark/cases/*.json into
plain Python objects and checks that each one is well-formed and
internally consistent. It does not call an AI provider, does not compare
anything against a model's actual output, and does not compute any score
- that is future work (#89's evaluation framework, #90's metrics), not
this module's job.

Both backend/tests/test_benchmark_dataset.py (today) and #89's future
runner are expected to import this module rather than re-implementing
loading/validation twice.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CASES_DIR = Path(__file__).resolve().parent / "cases"

# Kept in sync with the "Required Demo Datasets" / category list in
# benchmark/README.md; every case's tags must be drawn from this fixed
# vocabulary, the same way app/api/clinicalDocuments.ts's DOCUMENT_TYPES
# is a fixed, deliberately-chosen vocabulary rather than free text. This
# also doubles as the row list for the README's coverage table.
KNOWN_TAGS = {
    "straightforward_list",
    "narrative_text",
    "active_medication",
    "discontinued",
    "newly_started",
    "dose_change",
    "status_change",
    "multi_document",
    "conflicting_across_documents",
    "missing_fields",
    "prn",
    "route_variety",
    "frequency_variety",
    "brand_vs_generic",
    "abbreviation",
    "irrelevant_text",
    "mentioned_not_active",
    "reconciliation_relevant",
}

KNOWN_DIFFICULTIES = {"easy", "medium", "hard"}

CASE_ID_PATTERN_ERROR = "case_id must look like 'BENCH-###'"


@dataclass
class BenchmarkCase:
    """One benchmark case, loaded from a single JSON file.

    `raw` is the original parsed JSON (dict), kept alongside the typed
    fields so a future evaluation runner can round-trip it, or read a
    field this dataclass doesn't happen to surface, without needing this
    module to anticipate every future consumer's needs.
    """

    case_id: str
    tags: list[str]
    difficulty: str
    description: str
    input_notes: list[str]
    expected: dict[str, Any]
    source_path: Path
    raw: dict[str, Any]


class BenchmarkValidationError(Exception):
    """Raised for a single case that fails structural validation.

    Carries the offending case's id/path and the specific problems found,
    rather than failing on the first error, so a malformed dataset is
    diagnosable from one error message instead of a fix-one-rerun loop.
    """

    def __init__(self, identifier: str, problems: list[str]):
        self.identifier = identifier
        self.problems = problems
        super().__init__(f"{identifier}: {'; '.join(problems)}")


def _validate_medication_shape(medication: Any, index: int) -> list[str]:
    """Checks one entry of expected.medications against the real
    app.ai.schemas.Medication contract, without importing it directly -
    see validate_case() for why the import is deferred instead.
    """
    problems = []

    if not isinstance(medication, dict):
        return [f"expected.medications[{index}] is not an object"]

    if not medication.get("name") or not isinstance(medication["name"], str):
        problems.append(f"expected.medications[{index}].name must be a non-empty string")

    source_note = medication.get("source_note")
    if source_note is not None and not isinstance(source_note, int):
        problems.append(f"expected.medications[{index}].source_note must be an integer or null")

    return problems


def validate_case(case: dict[str, Any], identifier: str) -> list[str]:
    """Returns a list of human-readable problems with `case` (empty if
    none). Pure; never raises, never touches the filesystem, so it can
    be reused against a case that hasn't been loaded from disk yet (e.g.
    a future authoring tool checking a case before it's saved).
    """
    problems: list[str] = []

    case_id = case.get("case_id")
    if not isinstance(case_id, str) or not case_id.startswith("BENCH-") or len(case_id) != 9:
        problems.append(CASE_ID_PATTERN_ERROR)

    tags = case.get("tags")
    if not isinstance(tags, list) or not tags:
        problems.append("tags must be a non-empty list")
    else:
        unknown = sorted(set(tags) - KNOWN_TAGS)
        if unknown:
            problems.append(f"unknown tag(s): {', '.join(unknown)}")

    difficulty = case.get("difficulty")
    if difficulty not in KNOWN_DIFFICULTIES:
        problems.append(f"difficulty must be one of {sorted(KNOWN_DIFFICULTIES)}")

    description = case.get("description")
    if not isinstance(description, str) or not description.strip():
        problems.append("description must be a non-empty string")

    input_notes = case.get("input_notes")
    if not isinstance(input_notes, list) or not input_notes:
        problems.append("input_notes must be a non-empty list")
        input_notes = []
    else:
        for i, note in enumerate(input_notes):
            if not isinstance(note, str) or not note.strip():
                problems.append(f"input_notes[{i}] must be a non-empty string")

    expected = case.get("expected")
    if not isinstance(expected, dict):
        problems.append("expected must be an object")
        return problems

    medications = expected.get("medications")
    if not isinstance(medications, list):
        problems.append("expected.medications must be a list")
        medications = []

    for i, medication in enumerate(medications):
        problems.extend(_validate_medication_shape(medication, i))
        if isinstance(medication, dict):
            source_note = medication.get("source_note")
            if (
                isinstance(source_note, int)
                and input_notes
                and not (1 <= source_note <= len(input_notes))
            ):
                problems.append(
                    f"expected.medications[{i}].source_note={source_note} is out of "
                    f"range for {len(input_notes)} input note(s)"
                )

    inconsistencies = expected.get("possible_inconsistencies")
    if not isinstance(inconsistencies, list) or not all(
        isinstance(item, str) for item in inconsistencies
    ):
        problems.append("expected.possible_inconsistencies must be a list of strings")

    summary = expected.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        problems.append("expected.summary must be a non-empty string")

    # The strongest check: validate the whole `expected` object against
    # the real, production ClinicalSummary model (extra="forbid"), so a
    # field this hand-written validator doesn't happen to check, or a
    # typo'd/renamed field the real schema no longer has, fails loudly
    # here instead of silently drifting from the actual extraction
    # contract. Imported lazily, inside the function, so this module
    # stays importable (for tooling, or a case-authoring script) even in
    # a context where the backend package isn't on sys.path at all.
    try:
        from app.ai.schemas import ClinicalSummary

        ClinicalSummary.model_validate(expected)
    except ImportError:
        pass
    except Exception as error:  # pydantic.ValidationError
        problems.append(f"expected does not match app.ai.schemas.ClinicalSummary: {error}")

    return problems


def load_cases(cases_dir: Path | None = None) -> list[BenchmarkCase]:
    """Loads and validates every *.json file in `cases_dir` (defaults to
    benchmark/cases/). Raises BenchmarkValidationError on the first
    invalid case; raises a plain ValueError if any case_id repeats across
    files (case_id must be unique dataset-wide, not just per file).
    """
    directory = cases_dir or CASES_DIR
    paths = sorted(directory.glob("*.json"))

    if not paths:
        raise FileNotFoundError(f"No case files found in {directory}")

    cases: list[BenchmarkCase] = []
    seen_ids: dict[str, Path] = {}

    for path in paths:
        raw_text = path.read_text()
        try:
            raw = json.loads(raw_text)
        except json.JSONDecodeError as error:
            raise BenchmarkValidationError(str(path), [f"invalid JSON: {error}"]) from error

        problems = validate_case(raw, str(path))
        if problems:
            raise BenchmarkValidationError(str(path), problems)

        case_id = raw["case_id"]
        if path.stem != case_id:
            raise BenchmarkValidationError(
                str(path), [f"filename '{path.stem}' does not match case_id '{case_id}'"]
            )
        if case_id in seen_ids:
            raise BenchmarkValidationError(
                case_id, [f"duplicate case_id, also used by {seen_ids[case_id]}"]
            )
        seen_ids[case_id] = path

        cases.append(
            BenchmarkCase(
                case_id=case_id,
                tags=raw["tags"],
                difficulty=raw["difficulty"],
                description=raw["description"],
                input_notes=raw["input_notes"],
                expected=raw["expected"],
                source_path=path,
                raw=raw,
            )
        )

    return cases


def coverage_by_tag(cases: list[BenchmarkCase]) -> dict[str, list[str]]:
    """Maps each tag to the sorted list of case_ids carrying it, the
    data behind benchmark/README.md's coverage table, kept computable
    rather than hand-maintained so it can never drift from the actual
    case files.
    """
    coverage: dict[str, list[str]] = {tag: [] for tag in sorted(KNOWN_TAGS)}
    for case in cases:
        for tag in case.tags:
            coverage.setdefault(tag, []).append(case.case_id)

    return {tag: sorted(ids) for tag, ids in coverage.items()}


if __name__ == "__main__":
    loaded = load_cases()
    print(f"Loaded {len(loaded)} valid case(s) from {CASES_DIR}")
    for tag, ids in coverage_by_tag(loaded).items():
        print(f"  {tag}: {len(ids)} case(s) -> {', '.join(ids) if ids else '(none)'}")
