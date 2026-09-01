"""Tests for the model comparison report generator (benchmark/report/,
Issue #91). No test here makes a real network call, calls an AIProvider,
or reruns any benchmark case; fixtures are small, hand-built
BenchmarkCase/PredictionResult instances (the same #86/#89 dataclasses),
written to real tmp_path run directories and scored with the real,
unmodified `benchmark.metrics.cli.main` (Issue #90), so these tests
exercise the actual #90 output shape #91 reads, rather than a
hand-guessed metrics.json fixture that could drift from it.

benchmark/ is a top-level directory, a sibling of backend/ (see
benchmark/README.md); sys.path is extended here the same way
test_evaluation_runner.py/test_evaluation_metrics.py already do.
"""

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmark.loader import BenchmarkCase  # noqa: E402
from benchmark.metrics import cli as metrics_cli  # noqa: E402
from benchmark.report import charts  # noqa: E402
from benchmark.report import cli as report_cli  # noqa: E402
from benchmark.report.qualitative import build_qualitative_findings  # noqa: E402
from benchmark.report.render import render_report  # noqa: E402
from benchmark.report.sources import (  # noqa: E402
    ReportIntegrityError,
    load_all_sources,
    load_provider_source,
    parse_provider_mapping,
)
from benchmark.report.validation import validate_sources  # noqa: E402
from benchmark.runner.models import ParsingResult, PredictionResult, RunManifest  # noqa: E402
from benchmark.runner.models import benchmark_fingerprint as compute_fingerprint  # noqa: E402
from benchmark.runner.storage import PredictionWriter, write_manifest  # noqa: E402

# --- fixture builders (mirrors test_evaluation_metrics.py's own style) -----


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


def _case(case_id, tags=None, difficulty="easy", medications=None):
    medications = medications if medications is not None else [_med("Lisinopril", source_note=1)]
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
    possible_inconsistencies=None,
    summary="x",
    provider_call_succeeded=True,
    json_valid=True,
    schema_valid=True,
    provider_response=None,
    prompt_hash="sha256:test",
    latency_ms=100.0,
):
    parsed = None
    if provider_call_succeeded:
        if provider_response is None:
            provider_response = json.dumps(
                {
                    "medications": medications or [],
                    "possible_inconsistencies": possible_inconsistencies or [],
                    "summary": summary,
                }
            )
        if schema_valid:
            parsed = {
                "medications": medications or [],
                "possible_inconsistencies": possible_inconsistencies or [],
                "summary": summary,
            }

    return PredictionResult(
        run_id="test-run",
        case_id=case_id,
        case_tags=["straightforward_list"],
        provider=provider,
        model=model,
        inference_backend=None,
        prompt_hash=prompt_hash,
        provider_response=provider_response,
        provider_call_succeeded=provider_call_succeeded,
        parsing=ParsingResult(
            json_valid=json_valid,
            schema_valid=schema_valid,
            error_category=None,
            error_message=None,
        ),
        parsed_clinical_summary=parsed,
        latency_ms=latency_ms,
        timestamp="2026-01-01T00:00:00Z",
        generation_params={},
    ).to_dict()


class _DictAsResult:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


def _extract_section(markdown_text: str, heading: str) -> str:
    """The text of one top-level section, from `heading` up to (not
    including) the next "\\n\\n---\\n\\n" section separator render_report
    joins sections with, or the end of the document if `heading` is the
    last section. More robust than splitting on a bare "##", which would
    also match inside a "###" subsection heading.
    """
    start = markdown_text.index(heading)
    rest = markdown_text[start:]
    end = rest.find("\n\n---\n\n")
    return rest if end == -1 else rest[:end]


def _write_scored_run(
    tmp_path,
    monkeypatch,
    run_id,
    cases,
    predictions_by_provider,
    git_commit="abc1234",
    dirname=None,
):
    """Writes a real manifest.json + predictions.jsonl, then runs the
    real, unmodified benchmark.metrics.cli.main against it to produce a
    real metrics.json: the same artifact shape a real `python -m
    benchmark.metrics <run_dir>` invocation produces. Returns the run
    directory.

    monkeypatch.setattr(metrics_cli, "load_cases", ...) is required here
    the same way test_evaluation_metrics.py's own _write_run-equivalent
    tests need it: benchmark.metrics.cli.main() calls the real
    benchmark.loader.load_cases() otherwise, which would score against
    the real benchmark/cases/ dataset instead of this fixture's small,
    hand-built cases.
    """
    monkeypatch.setattr(metrics_cli, "load_cases", lambda: cases)
    run_dir = tmp_path / (dirname or run_id)
    run_dir.mkdir()
    providers = list(predictions_by_provider.keys())
    manifest = RunManifest(
        run_id=run_id,
        started_at="2026-01-01T00:00:00Z",
        completed_at="2026-01-01T00:01:00Z",
        status="complete",
        benchmark_fingerprint=compute_fingerprint(cases),
        case_count=len(cases),
        selected_providers=providers,
        case_filter=None,
        tag_filter=None,
        providers={
            p: {
                "model": f"{p}-model",
                "inference_backend": "ollama" if p != "gemini" else None,
                "generation_params": {},
                "runtime_version": "0.33.2" if p != "gemini" else None,
            }
            for p in providers
        },
        git_commit=git_commit,
        git_dirty=False,
        python_version="3.12.0",
        predictions_file="predictions.jsonl",
        result_count=sum(len(v) for v in predictions_by_provider.values()),
    )
    write_manifest(run_dir, manifest)

    with PredictionWriter(run_dir) as writer:
        for records in predictions_by_provider.values():
            for record_dict in records:
                writer.write(_DictAsResult(record_dict))

    metrics_cli.main([str(run_dir)])
    assert (run_dir / "metrics.json").exists()
    return run_dir


@pytest.fixture
def two_consistent_runs(tmp_path, monkeypatch):
    """Two run directories sharing the same cases/fingerprint/prompt
    hashes (as if from `benchmark.runner` with the same dataset state) -
    the case a real report should build successfully from, mirroring the
    real two-run workflow (Gemini from one run, others from another).
    """
    cases = [
        _case("BENCH-001", medications=[_med("Lisinopril", "10 mg", source_note=1)]),
        _case("BENCH-002", medications=[_med("Metformin", "500 mg", source_note=1)]),
    ]

    gemini_run = _write_scored_run(
        tmp_path,
        monkeypatch,
        "run-gemini",
        cases,
        {
            "gemini": [
                _prediction(
                    "BENCH-001", provider="gemini", medications=[_med("Lisinopril", "10 mg")]
                ),
                _prediction(
                    "BENCH-002", provider="gemini", medications=[_med("Metformin", "500 mg")]
                ),
            ]
        },
    )

    mixed_run = _write_scored_run(
        tmp_path,
        monkeypatch,
        "run-mixed",
        cases,
        {
            "openbiollm": [
                _prediction(
                    "BENCH-001",
                    provider="openbiollm",
                    provider_call_succeeded=True,
                    json_valid=False,
                    schema_valid=False,
                    provider_response="Note 2:\nPatient's medications are...",
                ),
                _prediction(
                    "BENCH-002",
                    provider="openbiollm",
                    provider_call_succeeded=True,
                    json_valid=False,
                    schema_valid=False,
                    provider_response="Note 2:\nMore fabricated note text...",
                ),
            ],
            "medgemma": [
                _prediction(
                    "BENCH-001",
                    provider="medgemma",
                    medications=[_med("Lisinopril", "10 mg")],
                    possible_inconsistencies=["Dose differs between notes."],
                ),
                _prediction(
                    "BENCH-002", provider="medgemma", medications=[_med("Metformin", "500 mg")]
                ),
            ],
        },
    )

    return gemini_run, mixed_run


# ============================================================================
# sources.py
# ============================================================================


def test_parse_provider_mapping_preserves_citation_order():
    mapping = parse_provider_mapping(["gemini=RUN_A", "openbiollm=RUN_B", "medgemma=RUN_B"])

    assert list(mapping.items()) == [
        ("gemini", "RUN_A"),
        ("openbiollm", "RUN_B"),
        ("medgemma", "RUN_B"),
    ]


@pytest.mark.parametrize("bad", ["no-equals-sign", "=missing-name", "missing-run-id="])
def test_parse_provider_mapping_rejects_malformed_values(bad):
    with pytest.raises(ReportIntegrityError):
        parse_provider_mapping([bad])


def test_parse_provider_mapping_rejects_empty_input():
    with pytest.raises(ReportIntegrityError):
        parse_provider_mapping([])


def test_parse_provider_mapping_rejects_duplicate_provider():
    with pytest.raises(ReportIntegrityError):
        parse_provider_mapping(["gemini=RUN_A", "gemini=RUN_B"])


def test_load_provider_source_success(two_consistent_runs):
    gemini_run, _mixed_run = two_consistent_runs

    source = load_provider_source("gemini", gemini_run.name, results_dir=gemini_run.parent)

    assert source.provider == "gemini"
    assert source.run_dir == gemini_run
    assert source.provider_manifest["model"] == "gemini-model"
    assert "reliability" in source.provider_metrics
    assert len(source.predictions) == 2


def test_load_provider_source_missing_run_dir_raises(tmp_path):
    with pytest.raises(ReportIntegrityError, match="No run directory"):
        load_provider_source("gemini", "does-not-exist", results_dir=tmp_path)


def test_load_provider_source_missing_metrics_json_raises(tmp_path):
    cases = [_case("BENCH-001")]
    run_dir = tmp_path / "unscored"
    run_dir.mkdir()
    manifest = RunManifest(
        run_id="unscored",
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
        result_count=1,
    )
    write_manifest(run_dir, manifest)
    with PredictionWriter(run_dir) as writer:
        writer.write(_DictAsResult(_prediction("BENCH-001")))

    with pytest.raises(ReportIntegrityError, match=r"metrics\.json"):
        load_provider_source("gemini", "unscored", results_dir=tmp_path)


def test_load_provider_source_unknown_provider_raises(two_consistent_runs):
    gemini_run, _mixed_run = two_consistent_runs

    with pytest.raises(ReportIntegrityError, match="was not selected"):
        load_provider_source("openbiollm", gemini_run.name, results_dir=gemini_run.parent)


# ============================================================================
# validation.py
# ============================================================================


def test_validate_sources_accepts_consistent_runs(two_consistent_runs):
    gemini_run, mixed_run = two_consistent_runs
    sources = load_all_sources(
        {"gemini": gemini_run.name, "openbiollm": mixed_run.name},
        results_dir=gemini_run.parent,
    )

    warnings = validate_sources(list(sources.values()))

    assert warnings == []


def test_validate_sources_rejects_fingerprint_mismatch(tmp_path, monkeypatch):
    cases_a = [_case("BENCH-001")]
    cases_b = [_case("BENCH-001", medications=[_med("Metformin", source_note=1)])]

    run_a = _write_scored_run(
        tmp_path,
        monkeypatch,
        "run-a",
        cases_a,
        {"gemini": [_prediction("BENCH-001", provider="gemini")]},
    )
    run_b = _write_scored_run(
        tmp_path,
        monkeypatch,
        "run-b",
        cases_b,
        {"medgemma": [_prediction("BENCH-001", provider="medgemma")]},
    )
    sources = load_all_sources({"gemini": run_a.name, "medgemma": run_b.name}, results_dir=tmp_path)

    with pytest.raises(ReportIntegrityError, match="benchmark_fingerprint mismatch"):
        validate_sources(list(sources.values()))


def test_validate_sources_rejects_case_set_mismatch(tmp_path, monkeypatch):
    # Both runs report the same benchmark_fingerprint (the full, two-case
    # dataset was identical at run time for both; benchmark_fingerprint
    # is computed over every loaded case, not just the ones a --cases
    # filter actually selected). What differs is which cases each run's
    # predictions.jsonl actually covers: run_a is a `--cases
    # BENCH-001`-filtered partial run, run_b a full one. This isolates
    # the case-set check from the fingerprint check above.
    full_dataset = [_case("BENCH-001"), _case("BENCH-002")]
    run_a = _write_scored_run(
        tmp_path,
        monkeypatch,
        "run-a",
        full_dataset,
        {"gemini": [_prediction("BENCH-001", provider="gemini")]},
    )
    run_b = _write_scored_run(
        tmp_path,
        monkeypatch,
        "run-b",
        full_dataset,
        {
            "medgemma": [
                _prediction("BENCH-001", provider="medgemma"),
                _prediction("BENCH-002", provider="medgemma"),
            ]
        },
    )
    sources = load_all_sources({"gemini": run_a.name, "medgemma": run_b.name}, results_dir=tmp_path)

    with pytest.raises(ReportIntegrityError, match="do not cover the same set"):
        validate_sources(list(sources.values()))


def test_validate_sources_rejects_prompt_hash_mismatch(tmp_path, monkeypatch):
    cases = [_case("BENCH-001")]
    run_a = _write_scored_run(
        tmp_path,
        monkeypatch,
        "run-a",
        cases,
        {"gemini": [_prediction("BENCH-001", provider="gemini", prompt_hash="sha256:aaa")]},
    )
    run_b = _write_scored_run(
        tmp_path,
        monkeypatch,
        "run-b",
        cases,
        {"medgemma": [_prediction("BENCH-001", provider="medgemma", prompt_hash="sha256:bbb")]},
    )
    sources = load_all_sources({"gemini": run_a.name, "medgemma": run_b.name}, results_dir=tmp_path)

    with pytest.raises(ReportIntegrityError, match="Prompt hash mismatch"):
        validate_sources(list(sources.values()))


def test_validate_sources_warns_but_does_not_raise_on_git_commit_mismatch(tmp_path, monkeypatch):
    cases = [_case("BENCH-001")]
    run_a = _write_scored_run(
        tmp_path,
        monkeypatch,
        "run-a",
        cases,
        {"gemini": [_prediction("BENCH-001", provider="gemini")]},
        git_commit="aaa1111",
    )
    run_b = _write_scored_run(
        tmp_path,
        monkeypatch,
        "run-b",
        cases,
        {"medgemma": [_prediction("BENCH-001", provider="medgemma")]},
        git_commit="bbb2222",
    )
    sources = load_all_sources({"gemini": run_a.name, "medgemma": run_b.name}, results_dir=tmp_path)

    warnings = validate_sources(list(sources.values()))

    assert len(warnings) == 1
    assert "different git commits" in warnings[0].message


# ============================================================================
# qualitative.py
# ============================================================================


def test_qualitative_findings_selects_non_empty_inconsistencies_deterministically():
    predictions = [
        _prediction("BENCH-003", possible_inconsistencies=["c"]),
        _prediction("BENCH-001", possible_inconsistencies=["a"]),
        _prediction("BENCH-002", possible_inconsistencies=[]),
    ]

    findings = build_qualitative_findings("gemini", predictions)

    assert findings.non_empty_inconsistency_count == 2
    assert findings.schema_valid_count == 3
    assert [e.case_id for e in findings.inconsistency_examples] == ["BENCH-001", "BENCH-003"]


def test_qualitative_findings_is_deterministic_across_calls():
    predictions = [
        _prediction("BENCH-001", possible_inconsistencies=["a"]),
        _prediction("BENCH-002", possible_inconsistencies=["b"]),
    ]

    first = build_qualitative_findings("gemini", predictions)
    second = build_qualitative_findings("gemini", predictions)

    assert first == second


def test_qualitative_findings_falls_back_to_raw_response_when_zero_schema_valid():
    predictions = [
        _prediction(
            "BENCH-001",
            provider="openbiollm",
            json_valid=False,
            schema_valid=False,
            provider_response="Note 2:\nfabricated continuation",
        ),
    ]

    findings = build_qualitative_findings("openbiollm", predictions)

    assert findings.schema_valid_count == 0
    assert findings.inconsistency_examples == []
    assert findings.summary_examples == []
    assert len(findings.raw_response_examples) == 1
    assert findings.raw_response_examples[0].case_id == "BENCH-001"


def test_qualitative_findings_do_not_leak_between_providers_sharing_a_run(tmp_path, monkeypatch):
    """Regression test for a real bug: ProviderSource.predictions was one
    run's entire predictions.jsonl, unfiltered by provider, so a
    provider with zero schema-valid responses of its own (e.g.
    OpenBioLLM) could be attributed another provider's (e.g. MedGemma's)
    possible_inconsistencies/summary excerpts, since both share one
    predictions.jsonl file when cited from the same run directory: the
    normal case, not an edge case.
    """
    cases = [_case("BENCH-001"), _case("BENCH-002")]
    run_dir = _write_scored_run(
        tmp_path,
        monkeypatch,
        "shared-run",
        cases,
        {
            "medgemma": [
                _prediction(
                    "BENCH-001",
                    provider="medgemma",
                    possible_inconsistencies=["Dose differs between notes."],
                    summary="MedGemma's own summary text.",
                ),
                _prediction("BENCH-002", provider="medgemma"),
            ],
            "openbiollm": [
                _prediction(
                    "BENCH-001",
                    provider="openbiollm",
                    json_valid=False,
                    schema_valid=False,
                    provider_response="Note 2:\nOpenBioLLM's own fabricated continuation.",
                ),
                _prediction(
                    "BENCH-002",
                    provider="openbiollm",
                    json_valid=False,
                    schema_valid=False,
                    provider_response="Note 2:\nAnother OpenBioLLM fabrication.",
                ),
            ],
        },
    )

    # Both providers cited from the exact same run_id: the real bug's
    # precondition.
    sources = load_all_sources(
        {"medgemma": run_dir.name, "openbiollm": run_dir.name}, results_dir=run_dir.parent
    )

    assert all(record["provider"] == "medgemma" for record in sources["medgemma"].predictions)
    assert all(record["provider"] == "openbiollm" for record in sources["openbiollm"].predictions)

    openbiollm_findings = build_qualitative_findings(
        "openbiollm", sources["openbiollm"].predictions
    )
    medgemma_findings = build_qualitative_findings("medgemma", sources["medgemma"].predictions)

    assert openbiollm_findings.schema_valid_count == 0
    assert openbiollm_findings.non_empty_inconsistency_count == 0
    assert openbiollm_findings.inconsistency_examples == []
    assert openbiollm_findings.summary_examples == []
    assert len(openbiollm_findings.raw_response_examples) == 2
    assert all(
        "OpenBioLLM" in example.provider_response
        for example in openbiollm_findings.raw_response_examples
    )

    assert medgemma_findings.schema_valid_count == 2
    assert medgemma_findings.non_empty_inconsistency_count == 1
    assert medgemma_findings.inconsistency_examples[0].possible_inconsistencies == [
        "Dose differs between notes."
    ]
    assert medgemma_findings.summary_examples[0].summary == "MedGemma's own summary text."


def test_render_report_qualitative_section_does_not_leak_between_providers_sharing_a_run(
    two_consistent_runs,
):
    """Same regression, at the full render_report level: openbiollm and
    medgemma are cited from the same mixed_run in this fixture, mirroring
    the real official artifacts (both providers share
    20260901-170758-31889a).
    """
    markdown_text, _figures = _render(two_consistent_runs)

    qualitative_section = _extract_section(markdown_text, "## Qualitative Discussion")
    openbiollm_block = qualitative_section.split("### openbiollm")[1].split("### medgemma")[0]

    assert "Dose differs between notes." not in openbiollm_block
    assert "No schema-valid responses" in openbiollm_block


# ============================================================================
# charts.py
# ============================================================================


def test_bar_height_is_proportional_and_clamped():
    assert charts._bar_height(0.5, y_max=1.0, plot_height=100) == 50.0
    assert charts._bar_height(0.0, y_max=1.0, plot_height=100) == 0.0
    assert charts._bar_height(2.0, y_max=1.0, plot_height=100) == 100.0  # clamped, never overflows
    assert charts._bar_height(1.0, y_max=0.0, plot_height=100) == 0.0  # never divides by zero


def test_reliability_chart_contains_one_bar_group_per_provider():
    reliability_by_provider = {
        "gemini": {
            "provider_call_success_rate": 1.0,
            "json_validity_rate": 1.0,
            "schema_validity_rate": 1.0,
            "evaluable_case_rate": 1.0,
        },
        "openbiollm": {
            "provider_call_success_rate": 1.0,
            "json_validity_rate": 0.0,
            "schema_validity_rate": 0.0,
            "evaluable_case_rate": 0.0,
        },
    }

    svg = charts.reliability_chart(["gemini", "openbiollm"], reliability_by_provider)

    assert svg.startswith("<svg")
    assert svg.count("<rect") >= 2 * 4  # 2 providers x 4 rate series, plus legend swatches
    assert "gemini" in svg
    assert "openbiollm" in svg


def test_medication_detection_chart_is_valid_svg_shape():
    detection_by_provider = {
        "gemini": {"end_to_end": {"micro": {"precision": 0.9, "recall": 0.95, "f1": 0.92}}},
    }

    svg = charts.medication_detection_chart(["gemini"], detection_by_provider)

    assert svg.startswith("<svg")
    assert svg.rstrip().endswith("</svg>")


def test_medication_detection_chart_renders_precision_not_applicable_as_zero_height_labeled_na():
    detection_by_provider = {
        "gemini": {"end_to_end": {"micro": {"precision": 0.9, "recall": 0.95, "f1": 0.92}}},
        "openbiollm": {"end_to_end": {"micro": {"precision": 1.0, "recall": 0.0, "f1": 0.0}}},
    }

    svg = charts.medication_detection_chart(
        ["gemini", "openbiollm"],
        detection_by_provider,
        precision_not_applicable=frozenset({"openbiollm"}),
    )

    assert ">N/A<" in svg
    # openbiollm's own precision value (1.0, the vacuous #90 convention)
    # must never surface as a rendered percentage anywhere in the chart.
    assert "100%" not in svg


def test_latency_chart_handles_zero_successful_calls_without_dividing_by_zero():
    latency_by_provider = {
        "openbiollm": {"count": 0, "mean": 0.0, "median": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
    }

    svg = charts.latency_chart(["openbiollm"], latency_by_provider)

    assert svg.startswith("<svg")


# ============================================================================
# render.py
# ============================================================================


def _render(two_consistent_runs):
    gemini_run, mixed_run = two_consistent_runs
    sources = load_all_sources(
        {"gemini": gemini_run.name, "openbiollm": mixed_run.name, "medgemma": mixed_run.name},
        results_dir=gemini_run.parent,
    )
    provider_order = list(sources.keys())
    warnings = validate_sources(list(sources.values()))
    qualitative_by_provider = {
        provider: build_qualitative_findings(provider, source.predictions)
        for provider, source in sources.items()
    }
    return render_report(
        provider_order=provider_order,
        sources=sources,
        warnings=warnings,
        qualitative_by_provider=qualitative_by_provider,
        generated_at="2026-01-01T00:00:00Z",
        cli_invocation="python -m benchmark.report --provider gemini=x --provider openbiollm=y",
    )


def test_render_report_suppresses_conditional_metrics_for_zero_evaluable_provider(
    two_consistent_runs,
):
    markdown_text, _figures = _render(two_consistent_runs)

    assert "Not shown for: openbiollm" in markdown_text
    assert "**openbiollm**: not applicable, 0 evaluable cases." in markdown_text


def test_render_report_shows_conditional_metrics_for_evaluable_provider(two_consistent_runs):
    markdown_text, _figures = _render(two_consistent_runs)

    detection_section = _extract_section(markdown_text, "## Medication Detection")
    assert "### Conditional on valid output" in detection_section
    assert "medgemma" in detection_section.split("### Conditional on valid output")[1]


def test_render_report_shows_precision_as_not_applicable_for_zero_predicted_positives(
    two_consistent_runs,
):
    """OpenBioLLM predicted zero medications across all 30 cases (every
    response was schema-invalid, so end_to_end treats every one as an
    empty prediction): TP=0 and FP=0, which makes #90's own
    precision_recall_f1 report the mathematically vacuous 1.0. The
    report must never display that as an observed 100% precision.
    """
    markdown_text, _figures = _render(two_consistent_runs)

    executive_summary = _extract_section(markdown_text, "## Executive Summary")
    detection_section = _extract_section(markdown_text, "## Medication Detection")

    for section in (executive_summary, detection_section):
        rows = [line for line in section.splitlines() if line.startswith("| openbiollm")]
        assert rows, f"no openbiollm row found in section:\n{section}"
        assert "not applicable" in rows[0]
        assert "100.0%" not in rows[0]

    assert "mathematically correct but would read here" in detection_section


def test_render_report_keeps_recall_and_f1_numeric_when_precision_is_not_applicable(
    two_consistent_runs,
):
    markdown_text, _figures = _render(two_consistent_runs)

    detection_section = _extract_section(markdown_text, "## Medication Detection")
    end_to_end_row = next(
        line for line in detection_section.splitlines() if line.startswith("| openbiollm")
    )

    cells = [cell.strip() for cell in end_to_end_row.strip("|").split("|")]
    _provider, precision, recall, f1, _macro_f1 = cells
    assert precision == "not applicable"
    assert recall == "0.0%"
    assert f1 == "0.0%"


def test_render_report_does_not_mark_precision_not_applicable_for_a_real_predicted_positive(
    two_consistent_runs,
):
    # MedGemma has evaluable cases and real predicted medications, so its
    # precision must remain a real, numeric value, never suppressed.
    markdown_text, _figures = _render(two_consistent_runs)

    detection_section = _extract_section(markdown_text, "## Medication Detection")
    end_to_end_row = next(
        line for line in detection_section.splitlines() if line.startswith("| medgemma")
    )
    assert "not applicable" not in end_to_end_row


def test_render_report_includes_provenance_for_every_provider(two_consistent_runs):
    gemini_run, mixed_run = two_consistent_runs
    markdown_text, _figures = _render(two_consistent_runs)

    assert gemini_run.name in markdown_text
    assert mixed_run.name in markdown_text
    assert "gemini-model" in markdown_text


def test_render_report_qualitative_section_never_frames_counts_as_scoring_metrics(
    two_consistent_runs,
):
    markdown_text, _figures = _render(two_consistent_runs)

    qualitative_section = _extract_section(markdown_text, "## Qualitative Discussion")

    # The disclaimer sentence itself is allowed to name these words; what
    # must never happen is the count being presented *as* one (e.g. "67%
    # accuracy", "higher than", "better/worse").
    assert "not an accuracy, recall, or sensitivity metric" in qualitative_section
    for forbidden in ("better than", "worse than", "higher quality", "outperform"):
        assert forbidden not in qualitative_section.lower()


def test_render_report_includes_openbiollm_investigation_note(two_consistent_runs):
    markdown_text, _figures = _render(two_consistent_runs)

    notes_section = _extract_section(
        markdown_text, "## Notes on Providers with Zero Evaluable Cases"
    )

    assert "investigated before being accepted" in notes_section
    assert "did not establish a single root cause" in notes_section
    # Concrete, checkable observations, not a claim that the audit
    # identified the model itself as the cause.
    assert "All 30 OpenBioLLM inference calls in this run completed successfully" in notes_section
    assert "system-role persona message" in notes_section
    assert "not a claim that OpenBioLLM is universally unable" in notes_section


def test_render_report_openbiollm_note_never_claims_a_confirmed_root_cause(two_consistent_runs):
    markdown_text, _figures = _render(two_consistent_runs)

    notes_section = _extract_section(
        markdown_text, "## Notes on Providers with Zero Evaluable Cases"
    )

    for overclaim in ("confirmed root cause", "the model itself", "is the cause"):
        assert overclaim not in notes_section


def test_render_report_includes_limitations_section(two_consistent_runs):
    markdown_text, _figures = _render(two_consistent_runs)

    assert "## Limitations" in markdown_text
    assert "synthetic" in markdown_text
    assert "statistical significance" in markdown_text


def test_render_report_returns_a_figure_per_chart(two_consistent_runs):
    _markdown_text, figures = _render(two_consistent_runs)

    assert set(figures) == {
        "reliability.svg",
        "medication_detection.svg",
        "by_difficulty.svg",
        "by_tag.svg",
        "latency.svg",
    }
    for svg in figures.values():
        assert svg.startswith("<svg")


# ============================================================================
# Zero-evaluable "vacuous credit" suppression (regression: macro F1 and
# grouped breakdowns can look like real performance for a provider with
# zero evaluable cases, because a case with zero expected medications
# scores a vacuous 1.0 regardless of whether anything was ever actually
# predicted; see #90's precision_recall_f1 zero-denominator convention).
# ============================================================================


@pytest.fixture
def zero_evaluable_with_vacuous_groups(tmp_path, monkeypatch):
    """Two real-medication cases (openbiollm genuinely misses both, F1=0
    each) plus one zero-expected-medication case (openbiollm's schema-
    invalid response is still treated as an empty prediction, which
    matches "nothing expected" vacuously, F1=1.0). Difficulty/tags are
    arranged so the vacuous case is alone in its own difficulty ("hard")
    and tag ("irrelevant_text") group, reproducing the exact reported
    bug: a zero-evaluable provider appearing to "score" 100% on a group
    made up entirely of such cases. medgemma is included as a genuinely
    evaluable provider with correct predictions everywhere (including
    correctly predicting no medications for the zero-expected case), so
    these tests can also confirm suppression is scoped to the zero-
    evaluable provider only, never applied blanket.
    """
    cases = [
        _case(
            "BENCH-001",
            tags=["straightforward_list"],
            difficulty="easy",
            medications=[_med("Lisinopril", "10 mg", source_note=1)],
        ),
        _case(
            "BENCH-002",
            tags=["straightforward_list"],
            difficulty="easy",
            medications=[_med("Metformin", "500 mg", source_note=1)],
        ),
        _case("BENCH-003", tags=["irrelevant_text"], difficulty="hard", medications=[]),
    ]

    run_dir = _write_scored_run(
        tmp_path,
        monkeypatch,
        "vacuous-groups-run",
        cases,
        {
            "openbiollm": [
                _prediction(
                    "BENCH-001",
                    provider="openbiollm",
                    json_valid=False,
                    schema_valid=False,
                    provider_response="Note 2:\nfabricated continuation one",
                ),
                _prediction(
                    "BENCH-002",
                    provider="openbiollm",
                    json_valid=False,
                    schema_valid=False,
                    provider_response="Note 2:\nfabricated continuation two",
                ),
                _prediction(
                    "BENCH-003",
                    provider="openbiollm",
                    json_valid=False,
                    schema_valid=False,
                    provider_response="Note 2:\nfabricated continuation three",
                ),
            ],
            "medgemma": [
                _prediction(
                    "BENCH-001", provider="medgemma", medications=[_med("Lisinopril", "10 mg")]
                ),
                _prediction(
                    "BENCH-002", provider="medgemma", medications=[_med("Metformin", "500 mg")]
                ),
                _prediction("BENCH-003", provider="medgemma", medications=[]),
            ],
        },
    )

    return run_dir


def _render_vacuous(run_dir):
    sources = load_all_sources(
        {"openbiollm": run_dir.name, "medgemma": run_dir.name}, results_dir=run_dir.parent
    )
    provider_order = list(sources.keys())
    warnings = validate_sources(list(sources.values()))
    qualitative_by_provider = {
        provider: build_qualitative_findings(provider, source.predictions)
        for provider, source in sources.items()
    }
    return render_report(
        provider_order=provider_order,
        sources=sources,
        warnings=warnings,
        qualitative_by_provider=qualitative_by_provider,
        generated_at="2026-01-01T00:00:00Z",
        cli_invocation="python -m benchmark.report --provider openbiollm=x --provider medgemma=x",
    )


def test_zero_evaluable_provider_would_otherwise_show_a_misleading_nonzero_macro_f1(
    zero_evaluable_with_vacuous_groups,
):
    # Confirms the fixture actually reproduces the reported bug: #90's own
    # stored macro F1 for openbiollm here is a nonzero 33.3% (mean of
    # 0, 0, and a vacuous 1.0), never touched or recomputed by this test,
    # purely read back to prove the suppression below is fixing a real,
    # observable problem and not a hypothetical one.
    run_dir = zero_evaluable_with_vacuous_groups
    metrics = json.loads((run_dir / "metrics.json").read_text())
    stored_macro_f1 = metrics["providers"]["openbiollm"]["medication_detection"]["end_to_end"][
        "macro"
    ]["f1"]

    assert stored_macro_f1 == pytest.approx(1 / 3)


def test_render_report_suppresses_macro_f1_for_zero_evaluable_provider(
    zero_evaluable_with_vacuous_groups,
):
    markdown_text, _figures = _render_vacuous(zero_evaluable_with_vacuous_groups)

    detection_section = _extract_section(markdown_text, "## Medication Detection")
    openbiollm_row = next(
        line for line in detection_section.splitlines() if line.startswith("| openbiollm")
    )
    cells = [cell.strip() for cell in openbiollm_row.strip("|").split("|")]
    _provider, precision, recall, f1_micro, f1_macro = cells

    assert precision == "not applicable"
    assert f1_macro == "not applicable"
    assert recall == "0.0%"
    assert f1_micro == "0.0%"
    assert "33.3%" not in detection_section


def test_render_report_keeps_macro_f1_numeric_for_an_evaluable_provider(
    zero_evaluable_with_vacuous_groups,
):
    markdown_text, _figures = _render_vacuous(zero_evaluable_with_vacuous_groups)

    detection_section = _extract_section(markdown_text, "## Medication Detection")
    medgemma_row = next(
        line for line in detection_section.splitlines() if line.startswith("| medgemma")
    )
    assert "not applicable" not in medgemma_row
    assert "100.0%" in medgemma_row


def test_render_report_suppresses_difficulty_breakdown_for_zero_evaluable_provider(
    zero_evaluable_with_vacuous_groups,
):
    markdown_text, _figures = _render_vacuous(zero_evaluable_with_vacuous_groups)

    difficulty_section = _extract_section(markdown_text, "## Difficulty Breakdown")
    hard_row = next(line for line in difficulty_section.splitlines() if line.startswith("| hard"))

    cells = [cell.strip() for cell in hard_row.strip("|").split("|")]
    _group, openbiollm_cell, medgemma_cell = cells

    # Without suppression this cell would read "100.0% (n=1)": a vacuous
    # perfect score for a provider that produced zero evaluable output.
    assert openbiollm_cell == "not applicable"
    assert "100.0%" not in openbiollm_cell
    assert "100.0%" in medgemma_cell


def test_render_report_suppresses_tag_breakdown_for_zero_evaluable_provider(
    zero_evaluable_with_vacuous_groups,
):
    markdown_text, _figures = _render_vacuous(zero_evaluable_with_vacuous_groups)

    tag_section = _extract_section(markdown_text, "## Tag Breakdown")
    irrelevant_row = next(
        line for line in tag_section.splitlines() if line.startswith("| irrelevant_text")
    )

    cells = [cell.strip() for cell in irrelevant_row.strip("|").split("|")]
    _group, openbiollm_cell, medgemma_cell = cells

    assert openbiollm_cell == "not applicable"
    assert "100.0%" not in openbiollm_cell
    assert "100.0%" in medgemma_cell


def test_render_report_reliability_presentation_is_unaffected_by_vacuous_suppression(
    zero_evaluable_with_vacuous_groups,
):
    # Explicit regression guard for the standing requirement: reliability
    # numbers (call success, JSON/schema validity, evaluable case rate)
    # are genuine observed results and must never be suppressed or
    # reworded by this change.
    markdown_text, _figures = _render_vacuous(zero_evaluable_with_vacuous_groups)

    reliability_section = _extract_section(markdown_text, "## Reliability")
    openbiollm_row = next(
        line for line in reliability_section.splitlines() if line.startswith("| openbiollm")
    )
    cells = [cell.strip() for cell in openbiollm_row.strip("|").split("|")]
    _provider, _attempted, call_success, json_validity, schema_validity, evaluable_rate = cells

    assert call_success == "100.0%"
    assert json_validity == "0.0%"
    assert schema_validity == "0.0%"
    assert evaluable_rate == "0.0%"
    assert "not applicable" not in reliability_section


def test_group_breakdown_chart_marks_zero_evaluable_provider_as_not_applicable():
    f1_by_provider_and_group = {
        "openbiollm": {"hard": {"micro": {"f1": 1.0}, "n": 1}},
        "medgemma": {"hard": {"micro": {"f1": 1.0}, "n": 1}},
    }

    svg = charts.group_breakdown_chart(
        "F1 by difficulty (end-to-end, micro)",
        ["openbiollm", "medgemma"],
        ["hard"],
        f1_by_provider_and_group,
        not_applicable_providers=frozenset({"openbiollm"}),
    )

    assert ">N/A<" in svg
    # medgemma's real 100% must still render normally.
    assert "100%" in svg


def test_group_breakdown_chart_with_no_not_applicable_providers_renders_all_values():
    f1_by_provider_and_group = {
        "gemini": {"easy": {"micro": {"f1": 0.9}, "n": 3}},
    }

    svg = charts.group_breakdown_chart(
        "F1 by difficulty (end-to-end, micro)", ["gemini"], ["easy"], f1_by_provider_and_group
    )

    assert ">N/A<" not in svg
    assert "90%" in svg


# ============================================================================
# cli.py (end-to-end)
# ============================================================================


def test_cli_writes_report_and_figures(two_consistent_runs, tmp_path):
    gemini_run, mixed_run = two_consistent_runs
    output_dir = tmp_path / "report-output"

    exit_code = report_cli.main(
        [
            "--provider",
            f"gemini={gemini_run}",
            "--provider",
            f"openbiollm={mixed_run}",
            "--provider",
            f"medgemma={mixed_run}",
            "--output",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    report_text = (output_dir / "report.md").read_text()
    assert "# MedLens Model Evaluation Report" in report_text
    assert "gemini" in report_text
    assert "openbiollm" in report_text
    assert "medgemma" in report_text

    figure_files = sorted(p.name for p in (output_dir / "figures").glob("*.svg"))
    assert figure_files == [
        "by_difficulty.svg",
        "by_tag.svg",
        "latency.svg",
        "medication_detection.svg",
        "reliability.svg",
    ]


def test_cli_never_modifies_source_run_artifacts(two_consistent_runs, tmp_path):
    gemini_run, mixed_run = two_consistent_runs
    before = {
        path: path.read_bytes()
        for run_dir in (gemini_run, mixed_run)
        for path in (
            run_dir / "manifest.json",
            run_dir / "predictions.jsonl",
            run_dir / "metrics.json",
        )
    }

    report_cli.main(
        [
            "--provider",
            f"gemini={gemini_run}",
            "--provider",
            f"openbiollm={mixed_run}",
            "--output",
            str(tmp_path / "out"),
        ]
    )

    for path, original_bytes in before.items():
        assert path.read_bytes() == original_bytes


def test_cli_fails_loudly_when_metrics_json_missing(tmp_path, capsys):
    cases = [_case("BENCH-001")]
    run_dir = tmp_path / "unscored"
    run_dir.mkdir()
    manifest = RunManifest(
        run_id="unscored",
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
        result_count=1,
    )
    write_manifest(run_dir, manifest)
    with PredictionWriter(run_dir) as writer:
        writer.write(_DictAsResult(_prediction("BENCH-001")))

    exit_code = report_cli.main(
        ["--provider", f"gemini={run_dir}", "--output", str(tmp_path / "out")]
    )

    assert exit_code == 1
    assert "metrics.json" in capsys.readouterr().err
