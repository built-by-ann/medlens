"""Tests for the evaluation metrics scorer (benchmark/metrics/, Issue
#90). No test here makes a real network call or constructs an
AIProvider - fixtures are hand-built BenchmarkCase/PredictionResult
instances (the same dataclasses #86/#89 already define), never anything
loaded from the real benchmark/cases/ dataset, so these tests are
independent of its actual current content.

benchmark/ is a top-level directory, a sibling of backend/ (see
benchmark/README.md) - not part of the `app` package under test
everywhere else in this suite. sys.path is extended here the same way
test_benchmark_dataset.py/test_evaluation_runner.py already do.
"""

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmark.loader import BenchmarkCase  # noqa: E402
from benchmark.metrics import cli  # noqa: E402
from benchmark.metrics.matching import match_case, normalize_text  # noqa: E402
from benchmark.metrics.scoring import (  # noqa: E402
    macro_average,
    precision_recall_f1,
    score_attribute,
    score_by_difficulty,
    score_by_tag,
    score_latency,
    score_medication_detection,
    score_notes,
    score_reliability,
    score_source_note,
)
from benchmark.runner.models import ParsingResult, PredictionResult, RunManifest  # noqa: E402
from benchmark.runner.models import benchmark_fingerprint as compute_fingerprint  # noqa: E402
from benchmark.runner.storage import PredictionWriter, write_manifest  # noqa: E402

# --- fixture builders -------------------------------------------------------


def _med(name, dosage=None, route=None, frequency=None, status=None, notes=None, source_note=None):
    return {
        "name": name,
        "dosage": dosage,
        "route": route,
        "frequency": frequency,
        "status": status,
        "notes": notes,
        "source_note": source_note,
    }


def _case(case_id="BENCH-T1", tags=None, difficulty="easy", medications=None):
    medications = medications if medications is not None else []
    tags = tags or ["straightforward_list"]
    raw = {
        "case_id": case_id,
        "tags": tags,
        "difficulty": difficulty,
        "description": "test case",
        "input_notes": ["irrelevant note text"],
        "expected": {"medications": medications, "possible_inconsistencies": [], "summary": "x"},
    }
    return BenchmarkCase(
        case_id=case_id,
        tags=tags,
        difficulty=difficulty,
        description="test case",
        input_notes=raw["input_notes"],
        expected=raw["expected"],
        source_path=Path(f"/fake/{case_id}.json"),
        raw=raw,
    )


def _prediction(
    case_id,
    provider="gemini",
    model="test-model",
    medications=None,
    provider_call_succeeded=True,
    json_valid=True,
    schema_valid=True,
    error_category=None,
    error_message=None,
    latency_ms=100.0,
    case_tags=None,
):
    parsed = None
    provider_response = None
    if provider_call_succeeded:
        provider_response = json.dumps(
            {
                "medications": medications or [],
                "possible_inconsistencies": [],
                "summary": "x",
            }
        )
        if schema_valid:
            parsed = {
                "medications": medications or [],
                "possible_inconsistencies": [],
                "summary": "x",
            }

    return PredictionResult(
        run_id="test-run",
        case_id=case_id,
        case_tags=case_tags or ["straightforward_list"],
        provider=provider,
        model=model,
        inference_backend=None,
        prompt_hash="sha256:test",
        provider_response=provider_response,
        provider_call_succeeded=provider_call_succeeded,
        parsing=ParsingResult(
            json_valid=json_valid,
            schema_valid=schema_valid,
            error_category=error_category,
            error_message=error_message,
        ),
        parsed_clinical_summary=parsed,
        latency_ms=latency_ms,
        timestamp="2026-01-01T00:00:00Z",
        generation_params={},
    ).to_dict()


# ============================================================================
# Matching
# ============================================================================


def test_perfect_match():
    expected = [_med("Lisinopril", "10 mg", "oral", "once daily", source_note=1)]
    predicted = [_med("Lisinopril", "10 mg", "oral", "once daily", source_note=1)]

    result = match_case(expected, predicted)

    assert len(result.matched) == 1
    assert result.false_positives == []
    assert result.false_negatives == []
    assert result.matched[0].source_note_ambiguous is False


def test_false_positive_when_predicted_has_no_expected_match():
    expected = []
    predicted = [_med("Lisinopril")]

    result = match_case(expected, predicted)

    assert result.matched == []
    assert result.false_positives == predicted
    assert result.false_negatives == []


def test_false_negative_when_expected_has_no_predicted_match():
    expected = [_med("Lisinopril")]
    predicted = []

    result = match_case(expected, predicted)

    assert result.matched == []
    assert result.false_positives == []
    assert result.false_negatives == expected


def test_genuinely_different_names_never_match():
    expected = [_med("Lisinopril")]
    predicted = [_med("Metformin")]

    result = match_case(expected, predicted)

    assert result.matched == []
    assert len(result.false_positives) == 1
    assert len(result.false_negatives) == 1


def test_duplicate_names_resolved_by_dosage_route_frequency():
    # Mirrors BENCH-006's real amlodipine duplicate: two expected entries
    # sharing a name, genuinely distinguished by dosage.
    expected = [
        _med("Amlodipine", "10 mg", "oral", "once daily", source_note=1),
        _med("Amlodipine", "5 mg", "oral", "once daily", source_note=2),
    ]
    predicted = [
        _med("Amlodipine", "5 mg", "oral", "once daily"),
        _med("Amlodipine", "10 mg", "oral", "once daily"),
    ]

    result = match_case(expected, predicted)

    assert len(result.matched) == 2
    by_dosage = {pair.predicted["dosage"]: pair for pair in result.matched}
    assert by_dosage["10 mg"].expected["dosage"] == "10 mg"
    assert by_dosage["5 mg"].expected["dosage"] == "5 mg"
    assert not any(pair.source_note_ambiguous for pair in result.matched)


def test_duplicate_names_with_identical_dosage_route_frequency_are_ambiguous():
    # Mirrors BENCH-029's real lisinopril duplicate: two expected entries
    # with every field null except source_note - genuinely undecidable by
    # any permitted signal.
    expected = [
        _med("Lisinopril", source_note=2),
        _med("Lisinopril", source_note=3),
    ]
    predicted = [_med("Lisinopril"), _med("Lisinopril")]

    result = match_case(expected, predicted)

    assert len(result.matched) == 2
    assert all(pair.source_note_ambiguous for pair in result.matched)


def test_reordering_predicted_list_does_not_change_match_outcome():
    expected = [
        _med("Amlodipine", "10 mg", "oral", "once daily", source_note=1),
        _med("Amlodipine", "5 mg", "oral", "once daily", source_note=2),
    ]
    predicted = [
        _med("Amlodipine", "5 mg", "oral", "once daily"),
        _med("Amlodipine", "10 mg", "oral", "once daily"),
    ]
    reversed_predicted = list(reversed(predicted))

    result = match_case(expected, predicted)
    result_reversed = match_case(expected, reversed_predicted)

    def as_dosage_pairs(matched):
        return sorted((pair.predicted["dosage"], pair.expected["dosage"]) for pair in matched)

    assert as_dosage_pairs(result.matched) == as_dosage_pairs(result_reversed.matched)
    assert len(result.false_positives) == len(result_reversed.false_positives) == 0
    assert len(result.false_negatives) == len(result_reversed.false_negatives) == 0


def test_source_note_mismatch_does_not_alter_pairing():
    # dosage/route/frequency alone determine the pairing; predicted
    # source_note values are deliberately "wrong"/scrambled and must not
    # influence which predicted item pairs with which expected item.
    expected = [
        _med("Amlodipine", "10 mg", "oral", "once daily", source_note=1),
        _med("Amlodipine", "5 mg", "oral", "once daily", source_note=2),
    ]
    predicted = [
        _med("Amlodipine", "10 mg", "oral", "once daily", source_note=99),
        _med("Amlodipine", "5 mg", "oral", "once daily", source_note=1),
    ]

    result = match_case(expected, predicted)

    by_dosage = {pair.expected["dosage"]: pair for pair in result.matched}
    assert by_dosage["10 mg"].predicted["source_note"] == 99
    assert by_dosage["5 mg"].predicted["source_note"] == 1


def test_status_mismatch_does_not_alter_pairing():
    # Mirrors BENCH-006's real atorvastatin duplicate: dosage/route/
    # frequency identical, only status differs - status must not be used
    # to resolve the tie, so this remains ambiguous rather than being
    # "resolved" by status agreement.
    expected = [
        _med("Atorvastatin", "20 mg", "oral", "nightly", status="continue", source_note=1),
        _med("Atorvastatin", "20 mg", "oral", "nightly", status=None, source_note=2),
    ]
    predicted = [
        _med("Atorvastatin", "20 mg", "oral", "nightly", status=None),
        _med("Atorvastatin", "20 mg", "oral", "nightly", status="continue"),
    ]

    result = match_case(expected, predicted)

    assert len(result.matched) == 2
    assert all(pair.source_note_ambiguous for pair in result.matched)


def test_notes_mismatch_does_not_alter_pairing():
    expected = [
        _med("Amlodipine", "10 mg", "oral", "once daily", notes="increased from 5 mg"),
        _med("Amlodipine", "5 mg", "oral", "once daily", notes=None),
    ]
    predicted = [
        _med("Amlodipine", "10 mg", "oral", "once daily", notes="a totally different note"),
        _med("Amlodipine", "5 mg", "oral", "once daily", notes="also different"),
    ]

    result = match_case(expected, predicted)

    by_dosage = {pair.expected["dosage"]: pair for pair in result.matched}
    assert by_dosage["10 mg"].predicted["notes"] == "a totally different note"
    assert by_dosage["5 mg"].predicted["notes"] == "also different"


def test_name_normalization_handles_case_and_whitespace():
    expected = [_med("Lisinopril")]
    predicted = [_med("  LISINOPRIL  ")]

    result = match_case(expected, predicted)

    assert len(result.matched) == 1


def test_normalize_text_collapses_whitespace_and_casefolds():
    assert normalize_text("  10  mg ") == "10 mg"
    assert normalize_text("PO") == "po"
    assert normalize_text(None) is None
    # Deliberately distinct after normalization - no semantic aliasing.
    assert normalize_text("PO") != normalize_text("oral")
    assert normalize_text("10 mg") != normalize_text("10mg")


# ============================================================================
# Attributes
# ============================================================================


def test_score_attribute_correct_value():
    pairs = match_case([_med("X", dosage="10 mg")], [_med("X", dosage="10 mg")]).matched
    result = score_attribute(pairs, "dosage")
    assert result == {
        "matched_pairs": 1,
        "accuracy": 1.0,
        "accuracy_given_expected_non_null": 1.0,
        "hallucination_rate_given_expected_null": 0.0,
    }


def test_score_attribute_incorrect_value():
    pairs = match_case([_med("X", dosage="10 mg")], [_med("X", dosage="20 mg")]).matched
    result = score_attribute(pairs, "dosage")
    assert result["accuracy"] == 0.0
    assert result["accuracy_given_expected_non_null"] == 0.0


def test_score_attribute_expected_null_predicted_value_is_hallucination():
    pairs = match_case([_med("X", route=None)], [_med("X", route="oral")]).matched
    result = score_attribute(pairs, "route")
    assert result["hallucination_rate_given_expected_null"] == 1.0
    assert result["accuracy"] == 0.0


def test_score_attribute_expected_value_predicted_null_is_not_hallucination_but_incorrect():
    pairs = match_case([_med("X", route="oral")], [_med("X", route=None)]).matched
    result = score_attribute(pairs, "route")
    assert result["accuracy"] == 0.0
    assert result["accuracy_given_expected_non_null"] == 0.0
    assert result["hallucination_rate_given_expected_null"] == 0.0  # expected wasn't null


def test_score_attribute_both_null_counts_as_correct():
    pairs = match_case([_med("X", status=None)], [_med("X", status=None)]).matched
    result = score_attribute(pairs, "status")
    assert result["accuracy"] == 1.0
    assert result["accuracy_given_expected_non_null"] == 0.0  # denominator is 0
    assert result["hallucination_rate_given_expected_null"] == 0.0


def test_score_attribute_zero_matched_pairs_reports_zero_not_one():
    result = score_attribute([], "dosage")
    assert result == {
        "matched_pairs": 0,
        "accuracy": 0.0,
        "accuracy_given_expected_non_null": 0.0,
        "hallucination_rate_given_expected_null": 0.0,
    }


def test_score_notes_four_way_buckets():
    pairs = match_case(
        [
            _med("A", notes=None, source_note=1),
            _med("B", notes="real note", source_note=1),
            _med("C", notes="expected note", source_note=1),
            _med("D", notes=None, source_note=1),
        ],
        [
            _med("A", notes=None),
            _med("B", notes="different phrasing entirely"),
            _med("C", notes=None),
            _med("D", notes="hallucinated note"),
        ],
    ).matched

    result = score_notes(pairs)

    assert result == {
        "matched_pairs": 4,
        "both_null": 1,
        "both_non_null": 1,
        "under_annotated": 1,
        "over_annotated": 1,
    }


def test_score_source_note_correct_and_incorrect():
    pairs = match_case(
        [_med("A", source_note=1), _med("B", source_note=2)],
        [_med("A", source_note=1), _med("B", source_note=99)],
    ).matched

    result = score_source_note(pairs)

    assert result["matched_pairs"] == 2
    assert result["scoreable_pairs"] == 2
    assert result["excluded_ambiguous_pairs"] == 0
    assert result["accuracy"] == 0.5


def test_score_source_note_null_prediction_counts_as_incorrect():
    pairs = match_case([_med("A", source_note=1)], [_med("A", source_note=None)]).matched

    result = score_source_note(pairs)

    assert result["accuracy"] == 0.0


def test_score_source_note_excludes_ambiguous_pairs_from_denominator():
    pairs = match_case(
        [_med("Lisinopril", source_note=2), _med("Lisinopril", source_note=3)],
        [_med("Lisinopril"), _med("Lisinopril")],
    ).matched

    result = score_source_note(pairs)

    assert result["matched_pairs"] == 2
    assert result["scoreable_pairs"] == 0
    assert result["excluded_ambiguous_pairs"] == 2
    assert result["accuracy"] == 0.0  # 0/0 -> when_zero=0.0, not misleadingly 1.0


# ============================================================================
# Medication detection: precision/recall/F1, micro/macro, zero-denominator
# ============================================================================


def test_precision_recall_f1_normal_case():
    result = precision_recall_f1(tp=8, fp=1, fn=2)
    assert result["precision"] == pytest.approx(8 / 9)
    assert result["recall"] == pytest.approx(8 / 10)


def test_precision_recall_f1_nothing_expected_and_nothing_predicted_is_vacuously_perfect():
    result = precision_recall_f1(tp=0, fp=0, fn=0)
    assert result == {"tp": 0, "fp": 0, "fn": 0, "precision": 1.0, "recall": 1.0, "f1": 1.0}


def test_precision_recall_f1_over_extraction_on_empty_expected_scores_zero_f1():
    # Nothing expected, but something was predicted anyway (hallucinated).
    result = precision_recall_f1(tp=0, fp=3, fn=0)
    assert result["precision"] == 0.0
    assert result["recall"] == 1.0  # vacuous: nothing was there to miss
    assert result["f1"] == 0.0


def test_precision_recall_f1_under_extraction_on_nonempty_expected_scores_zero_f1():
    result = precision_recall_f1(tp=0, fp=0, fn=3)
    assert result["precision"] == 1.0  # vacuous: nothing wrong was said
    assert result["recall"] == 0.0
    assert result["f1"] == 0.0


def test_macro_average_of_multiple_cases():
    scores = [
        precision_recall_f1(tp=1, fp=0, fn=0),  # perfect
        precision_recall_f1(tp=0, fp=1, fn=1),  # p=0, r=0
    ]
    result = macro_average(scores)
    assert result["precision"] == pytest.approx(0.5)
    assert result["recall"] == pytest.approx(0.5)
    assert result["case_count"] == 2


def test_macro_average_of_zero_cases():
    assert macro_average([]) == {"precision": 0.0, "recall": 0.0, "f1": 0.0, "case_count": 0}


def test_score_medication_detection_micro_aggregates_across_cases():
    cases_by_id = {
        "C1": _case("C1", medications=[_med("Lisinopril"), _med("Metformin")]),
        "C2": _case("C2", medications=[_med("Aspirin")]),
    }
    predictions = [
        _prediction("C1", medications=[_med("Lisinopril")]),  # 1 TP, 1 FN
        _prediction("C2", medications=[_med("Aspirin"), _med("Ibuprofen")]),  # 1 TP, 1 FP
    ]

    detection, matched_pairs = score_medication_detection(cases_by_id, predictions)

    micro = detection["end_to_end"]["micro"]
    assert micro["tp"] == 2
    assert micro["fp"] == 1
    assert micro["fn"] == 1
    assert len(matched_pairs) == 2


def test_score_medication_detection_zero_medication_case_is_vacuously_perfect():
    cases_by_id = {"C1": _case("C1", medications=[])}
    predictions = [_prediction("C1", medications=[])]

    detection, _ = score_medication_detection(cases_by_id, predictions)

    assert detection["end_to_end"]["micro"]["precision"] == 1.0
    assert detection["end_to_end"]["micro"]["recall"] == 1.0
    assert detection["end_to_end"]["macro"]["f1"] == 1.0


def test_failed_case_with_expected_medications_contributes_all_as_false_negatives():
    cases_by_id = {"C1": _case("C1", medications=[_med("Lisinopril"), _med("Metformin")])}
    predictions = [_prediction("C1", schema_valid=False, json_valid=False)]

    detection, matched_pairs = score_medication_detection(cases_by_id, predictions)

    assert detection["end_to_end"]["micro"]["fn"] == 2
    assert detection["end_to_end"]["micro"]["tp"] == 0
    assert matched_pairs == []


def test_failed_case_with_zero_expected_medications_is_still_vacuously_perfect_end_to_end():
    # A documented, deliberate interaction: reliability metrics (not
    # medication F1) are what actually reveal this failure - see
    # score_reliability and benchmark/README.md.
    cases_by_id = {"C1": _case("C1", medications=[])}
    predictions = [_prediction("C1", schema_valid=False, json_valid=False)]

    detection, _ = score_medication_detection(cases_by_id, predictions)

    assert detection["end_to_end"]["micro"]["f1"] == 1.0


def test_conditional_on_valid_output_excludes_unevaluable_cases_entirely():
    cases_by_id = {
        "C1": _case("C1", medications=[_med("Lisinopril")]),
        "C2": _case("C2", medications=[_med("Metformin")]),
    }
    predictions = [
        _prediction("C1", schema_valid=False, json_valid=False),
        _prediction("C2", medications=[_med("Metformin")]),
    ]

    detection, _ = score_medication_detection(cases_by_id, predictions)

    # end_to_end counts both cases (C1 contributes an FN)
    assert detection["end_to_end"]["micro"]["fn"] == 1
    assert detection["end_to_end"]["macro"]["case_count"] == 2
    # conditional only ever saw C2
    assert detection["conditional_on_valid_output"]["evaluable_case_count"] == 1
    assert detection["conditional_on_valid_output"]["macro"]["case_count"] == 1
    assert detection["conditional_on_valid_output"]["micro"]["fn"] == 0


# ============================================================================
# Reliability
# ============================================================================


def test_reliability_all_valid():
    predictions = [_prediction("C1"), _prediction("C2")]
    result = score_reliability(predictions)
    assert result == {
        "attempted_cases": 2,
        "provider_call_success_rate": 1.0,
        "json_validity_rate": 1.0,
        "schema_validity_rate": 1.0,
        "evaluable_case_rate": 1.0,
    }


def test_reliability_provider_failure():
    predictions = [
        _prediction("C1", provider_call_succeeded=False, json_valid=False, schema_valid=False),
        _prediction("C2"),
    ]
    result = score_reliability(predictions)
    assert result["provider_call_success_rate"] == 0.5
    assert result["evaluable_case_rate"] == 0.5


def test_reliability_invalid_json():
    predictions = [_prediction("C1", json_valid=False, schema_valid=False), _prediction("C2")]
    result = score_reliability(predictions)
    assert result["provider_call_success_rate"] == 1.0  # both calls succeeded
    assert result["json_validity_rate"] == 0.5
    assert result["evaluable_case_rate"] == 0.5


def test_reliability_schema_invalid():
    predictions = [_prediction("C1", schema_valid=False), _prediction("C2")]
    result = score_reliability(predictions)
    assert result["json_validity_rate"] == 1.0  # both parsed as JSON fine
    assert result["schema_validity_rate"] == 0.5
    assert result["evaluable_case_rate"] == 0.5


def test_reliability_zero_attempts_reports_zero_not_one():
    result = score_reliability([])
    assert result["provider_call_success_rate"] == 0.0
    assert result["evaluable_case_rate"] == 0.0


# ============================================================================
# Latency
# ============================================================================


def test_latency_excludes_failed_calls():
    predictions = [
        _prediction("C1", latency_ms=100.0),
        _prediction("C2", latency_ms=200.0),
        _prediction(
            "C3",
            provider_call_succeeded=False,
            json_valid=False,
            schema_valid=False,
            latency_ms=1.0,
        ),
    ]

    result = score_latency(predictions)

    assert result["population"] == "provider_call_succeeded"
    assert result["count"] == 2
    assert result["mean"] == 150.0
    assert result["min"] == 100.0
    assert result["max"] == 200.0


def test_latency_p95_over_small_sample():
    predictions = [_prediction(f"C{i}", latency_ms=float(i)) for i in range(1, 11)]  # 1..10
    result = score_latency(predictions)
    # nearest-rank: ceil(0.95*10)=10th smallest value -> 10.0
    assert result["p95"] == 10.0


def test_latency_with_no_successful_calls():
    predictions = [
        _prediction("C1", provider_call_succeeded=False, json_valid=False, schema_valid=False)
    ]
    result = score_latency(predictions)
    assert result["count"] == 0
    assert result["mean"] == 0.0


# ============================================================================
# Grouping (difficulty / tags)
# ============================================================================


def test_score_by_difficulty_groups_and_reports_n():
    cases_by_id = {
        "C1": _case("C1", difficulty="easy", medications=[_med("A")]),
        "C2": _case("C2", difficulty="hard", medications=[_med("B")]),
        "C3": _case("C3", difficulty="easy", medications=[_med("C")]),
    }
    predictions = [
        _prediction("C1", medications=[_med("A")]),
        _prediction("C2", medications=[]),
        _prediction("C3", medications=[_med("C")]),
    ]

    result = score_by_difficulty(cases_by_id, predictions)

    assert result["easy"]["n"] == 2
    assert result["easy"]["micro"]["tp"] == 2
    assert result["hard"]["n"] == 1
    assert result["hard"]["micro"]["fn"] == 1


def test_score_by_tag_a_case_can_appear_in_multiple_groups():
    cases_by_id = {
        "C1": _case("C1", tags=["multi_document", "prn"], medications=[_med("A")]),
    }
    predictions = [_prediction("C1", medications=[_med("A")])]

    result = score_by_tag(cases_by_id, predictions)

    assert result["multi_document"]["n"] == 1
    assert result["prn"]["n"] == 1
    assert result["multi_document"]["micro"]["tp"] == 1
    assert result["prn"]["micro"]["tp"] == 1


# ============================================================================
# Artifacts: cli.py / io.py integration
# ============================================================================


def _write_run(tmp_path, cases, predictions_by_provider, status="complete", providers=("gemini",)):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = RunManifest(
        run_id="test-run",
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:01:00Z",
        status=status,
        benchmark_fingerprint=compute_fingerprint(cases),
        case_count=len(cases),
        selected_providers=list(providers),
        case_filter=None,
        tag_filter=None,
        providers={
            p: {"model": "test-model", "inference_backend": None, "generation_params": {}}
            for p in providers
        },
        git_commit=None,
        git_dirty=None,
        python_version="3.12.0",
        predictions_file="predictions.jsonl",
        result_count=sum(len(v) for v in predictions_by_provider.values()),
    )
    write_manifest(run_dir, manifest)

    with PredictionWriter(run_dir) as writer:
        for records in predictions_by_provider.values():
            for record_dict in records:
                writer.write(_DictAsResult(record_dict))

    return run_dir


class _DictAsResult:
    """Adapter so PredictionWriter.write() (which calls .to_dict()) can
    write an already-built plain dict - avoids re-threading every test's
    fixture through PredictionResult reconstruction.
    """

    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


def test_complete_run_scores_successfully(tmp_path, monkeypatch):
    cases = [_case("C1", medications=[_med("Lisinopril")])]
    monkeypatch.setattr(cli, "load_cases", lambda: cases)
    predictions = {
        "gemini": [_prediction("C1", provider="gemini", medications=[_med("Lisinopril")])]
    }
    run_dir = _write_run(tmp_path, cases, predictions)

    exit_code = cli.main([str(run_dir)])

    assert exit_code == 0
    metrics = json.loads((run_dir / "metrics.json").read_text())
    assert metrics["run_id"] == "test-run"
    assert metrics["case_count"] == 1
    assert metrics["run_status"] == "complete"
    assert metrics["partial"] is False
    assert metrics["fingerprint_mismatch"] is None
    assert metrics["providers"]["gemini"]["medication_detection"]["end_to_end"]["micro"]["tp"] == 1


def test_incomplete_run_refused_by_default(tmp_path, monkeypatch):
    cases = [_case("C1")]
    monkeypatch.setattr(cli, "load_cases", lambda: cases)
    run_dir = _write_run(tmp_path, cases, {"gemini": [_prediction("C1")]}, status="running")

    exit_code = cli.main([str(run_dir)])

    assert exit_code == 1
    assert not (run_dir / "metrics.json").exists()


def test_incomplete_run_scored_with_override(tmp_path, monkeypatch):
    cases = [_case("C1")]
    monkeypatch.setattr(cli, "load_cases", lambda: cases)
    run_dir = _write_run(tmp_path, cases, {"gemini": [_prediction("C1")]}, status="interrupted")

    exit_code = cli.main([str(run_dir), "--allow-incomplete"])

    assert exit_code == 0
    metrics = json.loads((run_dir / "metrics.json").read_text())
    assert metrics["partial"] is True
    assert metrics["run_status"] == "interrupted"
    assert metrics["overrides"]["allow_incomplete"] is True


def test_fingerprint_mismatch_refused_by_default(tmp_path, monkeypatch):
    original_cases = [_case("C1")]
    run_dir = _write_run(tmp_path, original_cases, {"gemini": [_prediction("C1")]})

    changed_cases = [_case("C1", medications=[_med("SomethingNew")])]
    monkeypatch.setattr(cli, "load_cases", lambda: changed_cases)

    exit_code = cli.main([str(run_dir)])

    assert exit_code == 1
    assert not (run_dir / "metrics.json").exists()


def test_fingerprint_mismatch_scored_with_override(tmp_path, monkeypatch):
    original_cases = [_case("C1")]
    run_dir = _write_run(tmp_path, original_cases, {"gemini": [_prediction("C1")]})

    changed_cases = [_case("C1", medications=[_med("SomethingNew")])]
    monkeypatch.setattr(cli, "load_cases", lambda: changed_cases)

    exit_code = cli.main([str(run_dir), "--allow-fingerprint-mismatch"])

    assert exit_code == 0
    metrics = json.loads((run_dir / "metrics.json").read_text())
    assert metrics["fingerprint_mismatch"]["recomputed_fingerprint"] == compute_fingerprint(
        changed_cases
    )
    assert metrics["overrides"]["allow_fingerprint_mismatch"] is True


def test_duplicate_case_provider_record_refused(tmp_path, monkeypatch):
    cases = [_case("C1")]
    monkeypatch.setattr(cli, "load_cases", lambda: cases)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = RunManifest(
        run_id="test-run",
        started_at="t",
        completed_at="t",
        status="complete",
        benchmark_fingerprint=compute_fingerprint(cases),
        case_count=1,
        selected_providers=["gemini"],
        case_filter=None,
        tag_filter=None,
        providers={"gemini": {"model": "m", "inference_backend": None, "generation_params": {}}},
        git_commit=None,
        git_dirty=None,
        python_version="3.12.0",
        predictions_file="predictions.jsonl",
        result_count=2,
    )
    write_manifest(run_dir, manifest)
    duplicate_record = _prediction("C1", provider="gemini")
    (run_dir / "predictions.jsonl").write_text(
        json.dumps(duplicate_record) + "\n" + json.dumps(duplicate_record) + "\n"
    )

    exit_code = cli.main([str(run_dir)])

    assert exit_code == 1
    assert not (run_dir / "metrics.json").exists()


def test_unknown_case_id_refused(tmp_path, monkeypatch):
    cases = [_case("C1")]
    monkeypatch.setattr(cli, "load_cases", lambda: cases)
    run_dir = _write_run(
        tmp_path, cases, {"gemini": [_prediction("C1"), _prediction("DOES-NOT-EXIST")]}
    )

    exit_code = cli.main([str(run_dir)])

    assert exit_code == 1
    assert not (run_dir / "metrics.json").exists()


def test_missing_provider_predictions_refused(tmp_path, monkeypatch):
    cases = [_case("C1")]
    monkeypatch.setattr(cli, "load_cases", lambda: cases)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = RunManifest(
        run_id="test-run",
        started_at="t",
        completed_at="t",
        status="complete",
        benchmark_fingerprint=compute_fingerprint(cases),
        case_count=1,
        selected_providers=["gemini", "openbiollm"],  # openbiollm never actually attempted
        case_filter=None,
        tag_filter=None,
        providers={
            "gemini": {"model": "m", "inference_backend": None, "generation_params": {}},
            "openbiollm": {
                "model": "m",
                "inference_backend": "featherless-ai",
                "generation_params": {},
            },
        },
        git_commit=None,
        git_dirty=None,
        python_version="3.12.0",
        predictions_file="predictions.jsonl",
        result_count=1,
    )
    write_manifest(run_dir, manifest)
    with PredictionWriter(run_dir) as writer:
        writer.write(_DictAsResult(_prediction("C1", provider="gemini")))

    exit_code = cli.main([str(run_dir)])

    assert exit_code == 1
    assert not (run_dir / "metrics.json").exists()


def test_existing_metrics_refused_then_force_overwrites(tmp_path, monkeypatch):
    cases = [_case("C1")]
    monkeypatch.setattr(cli, "load_cases", lambda: cases)
    run_dir = _write_run(tmp_path, cases, {"gemini": [_prediction("C1")]})
    (run_dir / "metrics.json").write_text('{"stale": true}')

    refused = cli.main([str(run_dir)])
    assert refused == 1
    assert json.loads((run_dir / "metrics.json").read_text()) == {"stale": True}

    forced = cli.main([str(run_dir), "--force"])
    assert forced == 0
    assert "stale" not in json.loads((run_dir / "metrics.json").read_text())


def test_metrics_json_is_valid_json_with_expected_top_level_keys(tmp_path, monkeypatch):
    cases = [_case("C1", medications=[_med("Lisinopril")])]
    monkeypatch.setattr(cli, "load_cases", lambda: cases)
    run_dir = _write_run(
        tmp_path, cases, {"gemini": [_prediction("C1", medications=[_med("Lisinopril")])]}
    )

    cli.main([str(run_dir)])

    metrics = json.loads((run_dir / "metrics.json").read_text())
    assert set(metrics.keys()) == {
        "run_id",
        "scored_at",
        "benchmark_fingerprint",
        "case_count",
        "run_status",
        "partial",
        "fingerprint_mismatch",
        "overrides",
        "providers",
    }
    provider_metrics = metrics["providers"]["gemini"]
    assert set(provider_metrics.keys()) == {
        "reliability",
        "medication_detection",
        "attributes",
        "latency_ms",
        "by_difficulty",
        "by_tag",
    }


def test_cli_never_imports_or_touches_ai_provider_classes():
    import benchmark.metrics.cli as cli_module
    import benchmark.metrics.io as io_module
    import benchmark.metrics.matching as matching_module
    import benchmark.metrics.scoring as scoring_module

    for module in (cli_module, io_module, matching_module, scoring_module):
        source = Path(module.__file__).read_text()
        assert "AIProvider(" not in source
        assert "GeminiProvider" not in source
        assert "OpenBioLLMProvider" not in source
        assert "MedGemmaProvider" not in source
