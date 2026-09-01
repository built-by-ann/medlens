"""Deterministic, descriptive-only excerpts of `possible_inconsistencies`
and `summary` (Issue #91), the two `ClinicalSummary` fields Issue #90
deliberately excludes from quantitative scoring, since there is no
ground-truth annotation to grade either against (see benchmark/README.md's
"Scoring an evaluation run" section).

Everything this module produces is presented as illustrative behavior
only, never as a quality signal: no ranking, no "better/worse" language,
no accuracy/recall/sensitivity framing, because none of those have a
defined ground truth here. render.py's qualitative section is
responsible for keeping that framing in the rendered text; this module
only selects which excerpts to show, by a fixed rule, so the same input
always produces the same excerpts (never hand-picked per report).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MAX_INCONSISTENCY_EXAMPLES = 3
MAX_SUMMARY_EXAMPLES = 2
# Only used as a fallback when a provider has zero schema-valid
# responses (nothing structured exists to excerpt at all); see
# OpenBioLLMProvider's own investigated behavior in docs/ai.md.
MAX_RAW_RESPONSE_EXAMPLES = 2


@dataclass(frozen=True)
class InconsistencyExample:
    case_id: str
    possible_inconsistencies: list[str]


@dataclass(frozen=True)
class SummaryExample:
    case_id: str
    summary: str


@dataclass(frozen=True)
class RawResponseExample:
    case_id: str
    provider_response: str


@dataclass(frozen=True)
class QualitativeFindings:
    provider: str
    # A raw frequency count: how often this provider's own output
    # happened to include a non-empty possible_inconsistencies list.
    # Presence, not correctness: #90 never checked whether an actual
    # ground-truth inconsistency existed for the model to notice, so
    # this must never be read as a detection rate.
    non_empty_inconsistency_count: int
    schema_valid_count: int
    inconsistency_examples: list[InconsistencyExample]
    summary_examples: list[SummaryExample]
    # Populated only when schema_valid_count == 0, when there is no
    # structured output to excerpt, so a small sample of the raw,
    # unparsed response is shown instead, explicitly labeled elsewhere
    # (render.py) as illustration, not scored data.
    raw_response_examples: list[RawResponseExample]


def build_qualitative_findings(provider: str, predictions: list[dict[str, Any]]) -> QualitativeFindings:
    """`predictions` is expected to already be one provider's own records
    (ProviderSource.predictions; see sources.py's _read_predictions,
    which filters by both the cited run and `record["provider"]`).
    Filtered again here, defensively, rather than trusted blindly: one
    run directory can hold several providers' records interleaved in a
    single predictions.jsonl, and a caller passing an unfiltered or
    wrongly-filtered list must never produce another provider's
    possible_inconsistencies/summary output attributed to this one.
    That mislabeling is exactly the bug this filter exists to make
    structurally impossible, not just avoided by convention.
    """
    predictions = [record for record in predictions if record["provider"] == provider]

    schema_valid = sorted(
        (record for record in predictions if record["parsing"]["schema_valid"]),
        key=lambda record: record["case_id"],
    )

    non_empty = [
        record
        for record in schema_valid
        if record["parsed_clinical_summary"]["possible_inconsistencies"]
    ]

    inconsistency_examples = [
        InconsistencyExample(
            case_id=record["case_id"],
            possible_inconsistencies=record["parsed_clinical_summary"]["possible_inconsistencies"],
        )
        for record in non_empty[:MAX_INCONSISTENCY_EXAMPLES]
    ]

    summary_examples = [
        SummaryExample(case_id=record["case_id"], summary=record["parsed_clinical_summary"]["summary"])
        for record in schema_valid[:MAX_SUMMARY_EXAMPLES]
    ]

    raw_response_examples: list[RawResponseExample] = []
    if not schema_valid:
        attempted = sorted(predictions, key=lambda record: record["case_id"])
        for record in attempted:
            if len(raw_response_examples) >= MAX_RAW_RESPONSE_EXAMPLES:
                break
            if record.get("provider_response"):
                raw_response_examples.append(
                    RawResponseExample(
                        case_id=record["case_id"], provider_response=record["provider_response"]
                    )
                )

    return QualitativeFindings(
        provider=provider,
        non_empty_inconsistency_count=len(non_empty),
        schema_valid_count=len(schema_valid),
        inconsistency_examples=inconsistency_examples,
        summary_examples=summary_examples,
        raw_response_examples=raw_response_examples,
    )
