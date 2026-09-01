"""Structural validation for the synthetic extraction benchmark dataset
(GitHub issue #86, benchmark/cases/*.json).

This does not run any AI provider and does not score anything; it only
catches malformed benchmark entries or ground-truth records (invalid
JSON, a missing/mistyped field, a source_note out of range, an
`expected` shape the real ClinicalSummary/Medication schema would
reject). Model execution and evaluation metrics are out of scope here
and land in a future issue's own test suite instead.

benchmark/ is a top-level directory, a sibling of backend/ (see
benchmark/README.md for why), not part of the `app` package under test
everywhere else in this suite. sys.path is extended here, rather than
adding a conftest.py fixture other tests would also pick up, since this
is the one test file that needs it.
"""

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmark.loader import (  # noqa: E402
    KNOWN_TAGS,
    BenchmarkCase,
    load_cases,
)


@pytest.fixture(scope="module")
def cases() -> list[BenchmarkCase]:
    return load_cases()


def test_benchmark_has_a_meaningful_number_of_cases(cases):
    # A floor, not an exact count; see benchmark/README.md for the
    # design goal of "carefully designed cases over volume." This guards
    # against someone accidentally deleting most of the dataset, not
    # against the dataset growing over time.
    assert len(cases) >= 25


def test_every_case_id_is_unique(cases):
    ids = [case.case_id for case in cases]
    assert len(ids) == len(set(ids))


def test_every_case_id_matches_its_filename(cases):
    for case in cases:
        assert case.source_path.stem == case.case_id


def test_every_tag_used_is_a_known_tag(cases):
    for case in cases:
        unknown = set(case.tags) - KNOWN_TAGS
        assert not unknown, f"{case.case_id} uses unknown tag(s): {unknown}"


def test_every_required_category_has_at_least_two_cases(cases):
    # The dataset design goal (see benchmark/README.md) is genuine
    # coverage of each required category, not just one token example -
    # this is what actually enforces that goal, rather than only
    # documenting it.
    coverage: dict[str, int] = dict.fromkeys(KNOWN_TAGS, 0)
    for case in cases:
        for tag in case.tags:
            coverage[tag] += 1

    under_covered = {tag: count for tag, count in coverage.items() if count < 2}
    assert not under_covered, f"tag(s) with fewer than 2 cases: {under_covered}"


def test_every_medication_source_note_is_in_range(cases):
    for case in cases:
        note_count = len(case.input_notes)
        for medication in case.expected["medications"]:
            source_note = medication.get("source_note")
            if source_note is not None:
                assert 1 <= source_note <= note_count, (
                    f"{case.case_id}: source_note={source_note} out of range for "
                    f"{note_count} input note(s)"
                )


def test_multi_document_tagged_cases_actually_have_multiple_notes(cases):
    for case in cases:
        if "multi_document" in case.tags:
            assert len(case.input_notes) >= 2, (
                f"{case.case_id} is tagged multi_document but has only "
                f"{len(case.input_notes)} input note(s)"
            )


def test_status_when_present_is_a_literal_substring_of_its_source_note(cases):
    # Deterministic, mechanical guard against exactly the drift this
    # dataset was audited for: the production prompt (app/ai/prompts.py)
    # instructs "record ... status exactly as that specific note states
    # them", never a canonical vocabulary word substituted for the
    # note's own wording, and never inferred from a heading with no
    # per-item status language. This does not parse clinical meaning out
    # of prose (that would be brittle); it only checks that whatever
    # literal text `status` holds actually appears, verbatim and
    # case-insensitively, in the one note it's attributed to. A future
    # case that writes status: "discontinued" for a note that only says
    # "stopped" fails this check immediately, without anyone needing to
    # re-read the whole dataset by hand again.
    for case in cases:
        for medication in case.expected["medications"]:
            status = medication.get("status")
            if status is None:
                continue

            source_note = medication["source_note"]
            note_text = case.input_notes[source_note - 1]
            assert status.lower() in note_text.lower(), (
                f"{case.case_id}: status={status!r} for {medication['name']!r} is not a "
                f"literal substring of note {source_note}"
            )


def test_expected_output_matches_the_real_clinical_summary_schema(cases):
    from app.ai.schemas import ClinicalSummary

    for case in cases:
        # Raises pydantic.ValidationError (failing this test with a clear
        # message) if a case's ground truth doesn't match the real,
        # production extraction contract, including extra="forbid", so
        # a typo'd or invented field is caught here, not discovered by
        # #89's future runner.
        ClinicalSummary.model_validate(case.expected)


def test_medications_with_the_same_name_in_different_notes_use_distinct_source_notes(cases):
    # Not a hard schema rule, but a real-dataset-quality check: if a case
    # extracts the same medication name from two different notes, the
    # whole point is usually that they came from different source_notes
    # (that's what makes it a multi-document/conflicting-info case at
    # all); two identical (name, source_note) pairs would mean a
    # medication was accidentally duplicated within the same note.
    for case in cases:
        seen: set[tuple[str, int | None]] = set()
        for medication in case.expected["medications"]:
            key = (medication["name"], medication.get("source_note"))
            assert key not in seen, (
                f"{case.case_id}: duplicate (name, source_note) entry {key} in expected.medications"
            )
            seen.add(key)
