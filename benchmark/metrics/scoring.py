"""Medication-extraction quality metrics for a completed #89 run (Issue
#90). Pure functions over already-loaded predictions/ground truth - no
file I/O (see io.py) and no provider calls of any kind.
"""

from __future__ import annotations

import statistics
from collections import Counter
from math import ceil
from typing import Any

from benchmark.loader import BenchmarkCase
from benchmark.metrics.matching import MatchedPair, match_case, normalize_text

ATTRIBUTE_FIELDS = ("dosage", "route", "frequency", "status")


def _safe_divide(numerator: int, denominator: int, when_zero: float) -> float:
    return numerator / denominator if denominator else when_zero


def precision_recall_f1(tp: int, fp: int, fn: int) -> dict[str, Any]:
    """Standard IR zero-denominator convention: precision is 1.0 when
    nothing was predicted (TP+FP == 0 - vacuously precise, nothing wrong
    was said); recall is 1.0 when nothing was expected (TP+FN == 0 -
    vacuously complete, nothing was there to miss). F1 is 0.0 whenever
    either precision or recall is a *genuine* (non-vacuous) 0 - i.e. a
    real over- or under-extraction - and the harmonic mean otherwise, so
    F1 is 1.0 only when both precision and recall are (whether genuinely
    or vacuously). See benchmark/README.md for the six real
    zero-expected-medication cases this convention is checked against.
    """
    precision = _safe_divide(tp, tp + fp, when_zero=1.0)
    recall = _safe_divide(tp, tp + fn, when_zero=1.0)
    f1 = (
        0.0
        if (precision == 0.0 or recall == 0.0)
        else 2 * precision * recall / (precision + recall)
    )
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def macro_average(per_case_scores: list[dict[str, Any]]) -> dict[str, Any]:
    """Unweighted mean of each case's own precision/recall/f1 - every
    case counts equally regardless of how many medications it has,
    unlike micro (see _detection_over/score_medication_detection).
    """
    count = len(per_case_scores)
    if count == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "case_count": 0}
    return {
        "precision": sum(s["precision"] for s in per_case_scores) / count,
        "recall": sum(s["recall"] for s in per_case_scores) / count,
        "f1": sum(s["f1"] for s in per_case_scores) / count,
        "case_count": count,
    }


def _detection_over(
    cases_by_id: dict[str, BenchmarkCase], predictions: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], Counter, list[MatchedPair]]:
    """Runs match_case for every record in `predictions`. A schema-invalid
    record's predicted medications are treated as an empty list (never
    inferred or recovered from provider_response - see docs/ai.md's
    "never repair" convention, which this mirrors for scoring) - the
    entire end_to_end/conditional_on_valid_output distinction
    (score_medication_detection, below) is just which set of records is
    passed in here, not two different matching implementations.
    """
    per_case_scores: list[dict[str, Any]] = []
    totals: Counter = Counter()
    matched_pairs: list[MatchedPair] = []

    for record in predictions:
        case = cases_by_id[record["case_id"]]
        schema_valid = record["parsing"]["schema_valid"]
        predicted_medications = (
            record["parsed_clinical_summary"]["medications"] if schema_valid else []
        )

        result = match_case(case.expected["medications"], predicted_medications)
        scores = precision_recall_f1(
            tp=len(result.matched), fp=len(result.false_positives), fn=len(result.false_negatives)
        )
        per_case_scores.append(scores)
        totals["tp"] += scores["tp"]
        totals["fp"] += scores["fp"]
        totals["fn"] += scores["fn"]
        matched_pairs.extend(result.matched)

    return per_case_scores, totals, matched_pairs


def score_medication_detection(
    cases_by_id: dict[str, BenchmarkCase], predictions: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[MatchedPair]]:
    """`predictions` is one provider's own records. Returns the full
    medication_detection section (end_to_end over every attempted case;
    conditional_on_valid_output over schema-valid cases only) plus every
    matched pair actually produced (always drawn from schema-valid cases
    only, by construction - an unevaluable case has no predicted
    medications to ever match anything with), for attribute/source_note/
    notes scoring downstream.
    """
    end_to_end_scores, end_to_end_totals, matched_pairs = _detection_over(cases_by_id, predictions)

    schema_valid_predictions = [r for r in predictions if r["parsing"]["schema_valid"]]
    conditional_scores, conditional_totals, _ = _detection_over(
        cases_by_id, schema_valid_predictions
    )

    return (
        {
            "end_to_end": {
                "micro": precision_recall_f1(
                    end_to_end_totals.get("tp", 0),
                    end_to_end_totals.get("fp", 0),
                    end_to_end_totals.get("fn", 0),
                ),
                "macro": macro_average(end_to_end_scores),
            },
            "conditional_on_valid_output": {
                "micro": precision_recall_f1(
                    conditional_totals.get("tp", 0),
                    conditional_totals.get("fp", 0),
                    conditional_totals.get("fn", 0),
                ),
                "macro": macro_average(conditional_scores),
                "evaluable_case_count": len(schema_valid_predictions),
            },
        },
        matched_pairs,
    )


def score_attribute(matched_pairs: list[MatchedPair], field: str) -> dict[str, Any]:
    """dosage/route/frequency/status: normalized-exact comparison only
    (see matching.normalize_text - no semantic/alias normalization).
    Three numbers, each with a precisely different denominator so a
    sparse field (status is null 73% of the time in this benchmark)
    can't produce a misleadingly high plain accuracy by mostly agreeing
    on null:

    - accuracy: correct / matched_pairs (both-null counts as correct).
    - accuracy_given_expected_non_null: correct / (pairs where expected
      is non-null) - "when there was something to extract, how often was
      it right."
    - hallucination_rate_given_expected_null: (predicted non-null when
      expected null) / (pairs where expected is null) - "how often was
      something invented where there was nothing to find."

    matched_pairs == 0 reports 0.0 for every rate (not 1.0 - unlike
    detection's vacuous-perfect convention, "no data" is not the same
    claim as "perfect," and the accompanying matched_pairs/count fields
    always disambiguate the two for a reader).
    """
    matched_count = len(matched_pairs)
    correct = 0
    expected_non_null = 0
    correct_given_expected_non_null = 0
    expected_null = 0
    hallucinated_given_expected_null = 0

    for pair in matched_pairs:
        expected_value = normalize_text(pair.expected.get(field))
        predicted_value = normalize_text(pair.predicted.get(field))
        is_correct = expected_value == predicted_value

        if is_correct:
            correct += 1

        if expected_value is not None:
            expected_non_null += 1
            if is_correct:
                correct_given_expected_non_null += 1
        else:
            expected_null += 1
            if predicted_value is not None:
                hallucinated_given_expected_null += 1

    return {
        "matched_pairs": matched_count,
        "accuracy": _safe_divide(correct, matched_count, when_zero=0.0),
        "accuracy_given_expected_non_null": _safe_divide(
            correct_given_expected_non_null, expected_non_null, when_zero=0.0
        ),
        "hallucination_rate_given_expected_null": _safe_divide(
            hallucinated_given_expected_null, expected_null, when_zero=0.0
        ),
    }


def score_notes(matched_pairs: list[MatchedPair]) -> dict[str, Any]:
    """notes is free text (see benchmark/README.md) - never exact-match
    or fuzzy-scored. Presence agreement only: did the model correctly
    recognize *that* an annotation-worthy note existed, regardless of its
    exact wording.
    """
    both_null = both_non_null = under_annotated = over_annotated = 0

    for pair in matched_pairs:
        expected_present = pair.expected.get("notes") is not None
        predicted_present = pair.predicted.get("notes") is not None

        if not expected_present and not predicted_present:
            both_null += 1
        elif expected_present and predicted_present:
            both_non_null += 1
        elif expected_present and not predicted_present:
            under_annotated += 1
        else:
            over_annotated += 1

    return {
        "matched_pairs": len(matched_pairs),
        "both_null": both_null,
        "both_non_null": both_non_null,
        "under_annotated": under_annotated,
        "over_annotated": over_annotated,
    }


def score_source_note(matched_pairs: list[MatchedPair]) -> dict[str, Any]:
    """Source-attribution accuracy, scored strictly after matching (see
    matching.py's module docstring for why source_note is never part of
    the match itself). Expected source_note is always non-null in the
    current benchmark; a predicted null counts as incorrect, never
    excused.

    Pairs flagged source_note_ambiguous (matching.py: a duplicate-name
    group where dosage/route/frequency tied across more than one
    equally-good assignment, so which expected item a given predicted
    item was paired with wasn't actually determined by any permitted
    signal) are excluded from this metric's denominator entirely, rather
    than scored right or wrong by what would be an arbitrary coin flip -
    see excluded_ambiguous_pairs.
    """
    scoreable = [pair for pair in matched_pairs if not pair.source_note_ambiguous]
    correct = sum(
        1
        for pair in scoreable
        if pair.predicted.get("source_note") == pair.expected.get("source_note")
    )

    return {
        "matched_pairs": len(matched_pairs),
        "scoreable_pairs": len(scoreable),
        "excluded_ambiguous_pairs": len(matched_pairs) - len(scoreable),
        "accuracy": _safe_divide(correct, len(scoreable), when_zero=0.0),
    }


def score_reliability(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    """Four rates, four different denominators, never merged into one
    composite and never folded into medication F1 beyond end_to_end's
    explicit failed-case-as-empty-prediction treatment (see
    _detection_over):

    - provider_call_success_rate: succeeded / attempted (every pair).
    - json_validity_rate: valid JSON / calls that succeeded at all.
    - schema_validity_rate: schema-valid / JSON that was valid at all.
    - evaluable_case_rate: schema-valid / attempted (unconditional) -
      the number that must always be read alongside
      conditional_on_valid_output's quality numbers.
    """
    attempted = len(predictions)
    succeeded = sum(1 for r in predictions if r["provider_call_succeeded"])
    json_valid = sum(1 for r in predictions if r["parsing"]["json_valid"])
    schema_valid = sum(1 for r in predictions if r["parsing"]["schema_valid"])

    return {
        "attempted_cases": attempted,
        "provider_call_success_rate": _safe_divide(succeeded, attempted, when_zero=0.0),
        "json_validity_rate": _safe_divide(json_valid, succeeded, when_zero=0.0),
        "schema_validity_rate": _safe_divide(schema_valid, json_valid, when_zero=0.0),
        "evaluable_case_rate": _safe_divide(schema_valid, attempted, when_zero=0.0),
    }


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile: the smallest value such that at least
    `pct`% of samples are less than or equal to it. Implemented by hand
    (rather than relying on statistics.quantiles' particular
    interpolation method) so the exact definition is unambiguous and
    trivially hand-verifiable in tests.
    """
    if not sorted_values:
        return 0.0
    rank = ceil(pct / 100 * len(sorted_values))
    index = min(max(rank - 1, 0), len(sorted_values) - 1)
    return sorted_values[index]


def score_latency(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    """Population is explicitly provider_call_succeeded == True only - a
    failed call's near-instant latency (e.g. a missing-credential check
    that never reaches the network) is not a measure of model/provider
    speed and would distort every statistic if included. `count` is
    always reported alongside so a reader can see how few samples (at
    most 30, one per benchmark case) back these numbers - this is not
    production-grade latency benchmarking.
    """
    values = sorted(r["latency_ms"] for r in predictions if r["provider_call_succeeded"])

    if not values:
        return {
            "population": "provider_call_succeeded",
            "count": 0,
            "mean": 0.0,
            "median": 0.0,
            "p95": 0.0,
            "min": 0.0,
            "max": 0.0,
        }

    return {
        "population": "provider_call_succeeded",
        "count": len(values),
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "p95": _percentile(values, 95),
        "min": values[0],
        "max": values[-1],
    }


def _group_detection(
    cases_by_id: dict[str, BenchmarkCase], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    """The compact {n, micro, macro} shape used by both by_difficulty and
    by_tag - end_to_end interpretation only (the designated primary
    interpretation), not doubled up with conditional_on_valid_output, to
    keep grouped breakdowns from exploding in size for what is meant to
    be a compact, at-a-glance view.
    """
    per_case_scores, totals, _ = _detection_over(cases_by_id, predictions)
    return {
        "n": len(predictions),
        "micro": precision_recall_f1(totals.get("tp", 0), totals.get("fp", 0), totals.get("fn", 0)),
        "macro": macro_average(per_case_scores),
    }


def score_by_difficulty(
    cases_by_id: dict[str, BenchmarkCase], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in predictions:
        difficulty = cases_by_id[record["case_id"]].difficulty
        groups.setdefault(difficulty, []).append(record)

    return {
        difficulty: _group_detection(cases_by_id, records)
        for difficulty, records in sorted(groups.items())
    }


def score_by_tag(
    cases_by_id: dict[str, BenchmarkCase], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    """A case can appear under more than one tag (matching the benchmark's
    own multi-tag design - see benchmark/README.md's coverage table), so
    `n` values across all tags do not sum to the provider's total case
    count. Every group reports its own `n`, some as small as 2 (the
    benchmark's own enforced minimum per tag) - never suppressed, but
    always alongside the sample size so a group's numbers are never read
    as more statistically meaningful than they are. Deciding whether a
    given group is *reliable enough* to draw a conclusion from belongs to
    #91, not this module.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for record in predictions:
        case = cases_by_id[record["case_id"]]
        for tag in case.tags:
            groups.setdefault(tag, []).append(record)

    return {tag: _group_detection(cases_by_id, records) for tag, records in sorted(groups.items())}
