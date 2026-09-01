"""Assembles the final report.md content for a comparison report (Issue
#91) from already-validated sources, already-computed #90 metrics, and
already-selected qualitative excerpts. A pure function with respect to
the filesystem: it returns (markdown_text, {filename: svg_text}) and
writes nothing itself; cli.py owns all file I/O, the same separation
`benchmark/metrics/scoring.py` (pure) vs. `benchmark/metrics/io.py`
(file I/O) already keeps.

Every number here is read from a provider's own already-written
metrics.json; nothing in this module recomputes a #90 metric, matches a
medication, or touches predictions.jsonl except for the two fields #90
never scores (possible_inconsistencies, summary) via qualitative.py.
"""

from __future__ import annotations

from benchmark.report import charts
from benchmark.report.qualitative import QualitativeFindings
from benchmark.report.sources import ProviderSource
from benchmark.report.validation import ValidationWarning

ATTRIBUTE_FIELDS = ("dosage", "route", "frequency", "status")

# Specific, investigated narrative for a provider known to have zero
# evaluable cases; see docs/ai.md's Provider Abstraction / Limitations
# sections for the full audit this text summarizes. A provider not
# listed here still gets a short, generic explanation (see
# _GENERIC_ZERO_EVALUABLE_NOTE) rather than silence.
_ZERO_EVALUABLE_PROVIDER_NOTES: dict[str, str] = {
    "openbiollm": (
        "All 30 OpenBioLLM inference calls in this run completed successfully. None of the 30 "
        "responses produced valid JSON under this benchmark's standardized protocol, so none were "
        "schema-valid or evaluable; every structured-output-dependent metric below is reported as "
        "not applicable rather than a misleading zero.\n\n"
        "This was investigated before being accepted as an official result, not assumed. The "
        "checks performed did not reveal an obvious adapter or configuration explanation: the "
        "local Modelfile uses Ollama's own official Llama-3-Instruct chat template verbatim; the "
        "OpenBioLLM GGUF's tokenizer registers the same Llama-3 special/control tokens, at the "
        "same vocabulary indices, as Ollama's reference `llama3:8b-instruct-q4_K_M` model; and a "
        "control test sending the identical benchmark prompt, through the identical request "
        "configuration, to that reference model produced a correct, schema-valid extraction while "
        "OpenBioLLM did not. The system-role persona message documented in OpenBioLLM's own model "
        "card usage example was also tested directly against this same prompt and did not resolve "
        "the behavior.\n\n"
        "The audit did not establish a single root cause. This result is an official measurement "
        "of OpenBioLLM's behavior under this benchmark's standardized protocol; it is not a claim "
        "that OpenBioLLM is universally unable to perform medication extraction, and it has not "
        "been discarded, repaired, or reinterpreted."
    ),
}

_GENERIC_ZERO_EVALUABLE_NOTE = (
    "Every call succeeded, but none of the responses were schema-valid, so every "
    "structured-output-dependent metric below is reported as not applicable rather than a "
    "misleading zero."
)


def _pct(value: float) -> str:
    return f"{value:.1%}"


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def _evaluable_count(source: ProviderSource) -> int:
    return source.provider_metrics["medication_detection"]["conditional_on_valid_output"][
        "evaluable_case_count"
    ]


def _zero_evaluable_cases(source: ProviderSource) -> bool:
    """True when this provider produced no structured output at all
    (zero evaluable cases). Gates suppression of every human-facing
    number that is downstream of having at least one real predicted
    medication list to work with: precision (see
    _precision_not_applicable, below), macro F1 (a per-case average, and
    a case with zero expected medications scores a vacuous 1.0 in it
    regardless of whether the provider ever produced real output,
    pulling the average up), and the by_difficulty/by_tag breakdowns
    (the same vacuous-credit problem, per group; a provider can appear to
    "score" 100% on a tag made up entirely of zero-expected-medication
    cases despite never having produced one evaluable response). #90's
    own stored metrics are never changed by any of this; only how this
    report chooses to display them for a provider with nothing behind
    the numbers.
    """
    return _evaluable_count(source) == 0


def _precision_not_applicable(source: ProviderSource) -> bool:
    """True when this provider's end-to-end precision is the
    mathematically conventional vacuous 1.0 (nothing predicted, so
    nothing predicted incorrectly), with zero evaluable cases behind it.
    That specific combination is the one place #90's own correct scoring
    convention would read, to a person skimming this report, as an
    observed 100% precision rather than what it actually is: no
    structured output was ever produced to be precise about. #90's own
    stored metric is never changed here, only how this report chooses to
    display it.
    """
    if not _zero_evaluable_cases(source):
        return False
    micro = source.provider_metrics["medication_detection"]["end_to_end"]["micro"]
    return micro["tp"] == 0 and micro["fp"] == 0


def _short_fingerprint(fingerprint: str) -> str:
    return fingerprint if len(fingerprint) <= 23 else fingerprint[:23] + "…"


def render_report(
    *,
    provider_order: list[str],
    sources: dict[str, ProviderSource],
    warnings: list[ValidationWarning],
    qualitative_by_provider: dict[str, QualitativeFindings],
    generated_at: str,
    cli_invocation: str,
) -> tuple[str, dict[str, str]]:
    figures: dict[str, str] = {}
    sections: list[str] = []

    sections.append(f"# MedLens Model Evaluation Report\n\nGenerated: {generated_at}")

    sections.append(_render_provenance(provider_order, sources, warnings, cli_invocation))
    sections.append(_render_executive_summary(provider_order, sources))
    sections.append(_render_reliability(provider_order, sources, figures))
    sections.append(_render_medication_detection(provider_order, sources, figures))
    sections.append(_render_attributes(provider_order, sources))
    sections.append(_render_group_breakdown(provider_order, sources, figures, key="by_difficulty"))
    sections.append(_render_group_breakdown(provider_order, sources, figures, key="by_tag"))
    sections.append(_render_latency(provider_order, sources, figures))
    sections.append(_render_qualitative(provider_order, qualitative_by_provider))
    sections.append(_render_zero_evaluable_notes(provider_order, sources))
    sections.append(_render_limitations())
    sections.append(_render_appendix(provider_order, sources, cli_invocation))

    markdown_text = "\n\n---\n\n".join(section for section in sections if section) + "\n"
    return markdown_text, figures


def _render_provenance(
    provider_order: list[str],
    sources: dict[str, ProviderSource],
    warnings: list[ValidationWarning],
    cli_invocation: str,
) -> str:
    rows = []
    for provider in provider_order:
        source = sources[provider]
        provider_manifest = source.provider_manifest
        rows.append(
            [
                provider,
                source.run_id,
                provider_manifest.get("model", ""),
                str(provider_manifest.get("inference_backend") or "-"),
                str(provider_manifest.get("runtime_version") or "-"),
                source.manifest.get("git_commit") or "-",
                _short_fingerprint(source.manifest["benchmark_fingerprint"]),
            ]
        )

    table = _md_table(
        ["Provider", "Source run", "Model", "Backend", "Runtime", "Git commit", "Fingerprint"],
        rows,
    )

    warning_text = ""
    if warnings:
        warning_lines = "\n".join(f"- **Warning:** {w.message}" for w in warnings)
        warning_text = f"\n\n{warning_lines}"

    return (
        "## Provenance\n\n"
        f"Generated by: `{cli_invocation}`\n\n"
        f"{table}"
        f"{warning_text}\n\n"
        "Every cited run was verified to share the same `benchmark_fingerprint` (dataset state) "
        "and the same per-case `prompt_hash` (exact prompt text) for every case in common; see "
        "benchmark/report/validation.py. A provider's numbers below always come from exactly one "
        "source run, named above."
    )


def _render_executive_summary(provider_order: list[str], sources: dict[str, ProviderSource]) -> str:
    rows = []
    any_not_applicable = False
    for provider in provider_order:
        source = sources[provider]
        detection = source.provider_metrics["medication_detection"]["end_to_end"]["micro"]
        reliability = source.provider_metrics["reliability"]
        precision_text = "not applicable"
        if not _precision_not_applicable(source):
            precision_text = _pct(detection["precision"])
        else:
            any_not_applicable = True
        rows.append(
            [
                provider,
                precision_text,
                _pct(detection["recall"]),
                _pct(detection["f1"]),
                _pct(reliability["evaluable_case_rate"]),
            ]
        )

    table = _md_table(
        ["Provider", "Precision", "Recall", "F1", "Evaluable case rate"],
        rows,
    )

    precision_note = ""
    if any_not_applicable:
        precision_note = (
            '\n\nPrecision is shown as "not applicable" for a provider with zero evaluable '
            "cases and zero predicted medications, rather than the mathematically conventional "
            "100% (nothing predicted, so nothing predicted incorrectly). See Medication "
            "Detection below for the full explanation; #90's own stored metric is unchanged, "
            "only its display here."
        )

    return (
        "## Executive Summary\n\n"
        "End-to-end micro medication-detection scores across all 30 attempted cases per provider, "
        "and the share of cases each provider produced schema-valid, evaluable output for. See "
        "Medication Detection and Reliability below for the full breakdown, and the notes further "
        "down for why a low evaluable case rate changes how the other numbers should be read."
        f"{precision_note}\n\n"
        f"{table}"
    )


def _render_reliability(
    provider_order: list[str], sources: dict[str, ProviderSource], figures: dict[str, str]
) -> str:
    reliability_by_provider = {
        provider: sources[provider].provider_metrics["reliability"] for provider in provider_order
    }
    rows = [
        [
            provider,
            str(reliability_by_provider[provider]["attempted_cases"]),
            _pct(reliability_by_provider[provider]["provider_call_success_rate"]),
            _pct(reliability_by_provider[provider]["json_validity_rate"]),
            _pct(reliability_by_provider[provider]["schema_validity_rate"]),
            _pct(reliability_by_provider[provider]["evaluable_case_rate"]),
        ]
        for provider in provider_order
    ]
    table = _md_table(
        [
            "Provider",
            "Attempted",
            "Call success",
            "JSON validity",
            "Schema validity",
            "Evaluable case rate",
        ],
        rows,
    )

    figures["reliability.svg"] = charts.reliability_chart(provider_order, reliability_by_provider)

    return (
        "## Reliability\n\n"
        "`json_validity_rate` is computed over calls that succeeded at all; `schema_validity_rate` "
        "over responses that were valid JSON at all: each rate has its own denominator, not the "
        "total attempted count (see benchmark/README.md). A provider can have a perfect "
        "call-success rate and a zero schema-validity rate at the same time; that combination is "
        "a real, distinct outcome, not a contradiction. See the reliability chart below.\n\n"
        f"{table}\n\n"
        "![Reliability](figures/reliability.svg)"
    )


def _render_medication_detection(
    provider_order: list[str], sources: dict[str, ProviderSource], figures: dict[str, str]
) -> str:
    detection_by_provider = {
        provider: sources[provider].provider_metrics["medication_detection"]
        for provider in provider_order
    }

    precision_not_applicable = frozenset(
        provider for provider in provider_order if _precision_not_applicable(sources[provider])
    )
    zero_evaluable = frozenset(
        provider for provider in provider_order if _zero_evaluable_cases(sources[provider])
    )

    end_to_end_rows = []
    for provider in provider_order:
        micro = detection_by_provider[provider]["end_to_end"]["micro"]
        precision_text = (
            "not applicable" if provider in precision_not_applicable else _pct(micro["precision"])
        )
        macro_f1_text = (
            "not applicable"
            if provider in zero_evaluable
            else _pct(detection_by_provider[provider]["end_to_end"]["macro"]["f1"])
        )
        end_to_end_rows.append(
            [
                provider,
                precision_text,
                _pct(micro["recall"]),
                _pct(micro["f1"]),
                macro_f1_text,
            ]
        )
    end_to_end_table = _md_table(
        ["Provider", "Precision (micro)", "Recall (micro)", "F1 (micro)", "F1 (macro)"],
        end_to_end_rows,
    )

    precision_note = ""
    if precision_not_applicable:
        precision_note = (
            '\n\nPrecision is reported as "not applicable" for '
            + ", ".join(sorted(precision_not_applicable))
            + ": with zero evaluable cases and zero predicted medications, #90's own scoring "
            "convention (precision is 1.0 when nothing was predicted, since nothing was "
            "predicted incorrectly) is mathematically correct but would read here as an "
            "observed 100% precision. Recall and micro F1 are still shown numerically (0%), "
            "since the expected medications genuinely became false negatives under the "
            "end-to-end policy."
        )

    macro_f1_note = ""
    if zero_evaluable:
        macro_f1_note = (
            '\n\nF1 (macro) is likewise reported as "not applicable" for '
            + ", ".join(sorted(zero_evaluable))
            + ": macro F1 averages each case's own F1, and a case where zero medications were "
            "expected scores a vacuous 1.0 in that average regardless of whether the provider "
            "produced any real output, which can pull the average visibly above zero even "
            "though nothing was ever evaluable."
        )

    conditional_rows = []
    excluded = []
    for provider in provider_order:
        evaluable = _evaluable_count(sources[provider])
        if evaluable == 0:
            excluded.append(provider)
            continue
        conditional = detection_by_provider[provider]["conditional_on_valid_output"]
        conditional_rows.append(
            [
                provider,
                str(evaluable),
                _pct(conditional["micro"]["precision"]),
                _pct(conditional["micro"]["recall"]),
                _pct(conditional["micro"]["f1"]),
            ]
        )

    conditional_section = ""
    if conditional_rows:
        conditional_table = _md_table(
            ["Provider", "Evaluable cases", "Precision (micro)", "Recall (micro)", "F1 (micro)"],
            conditional_rows,
        )
        conditional_section = f"\n\n### Conditional on valid output\n\n{conditional_table}"
    if excluded:
        conditional_section += (
            "\n\nNot shown for: "
            + ", ".join(excluded)
            + " (0 evaluable cases; see the notes further down)."
        )

    figures["medication_detection.svg"] = charts.medication_detection_chart(
        provider_order, detection_by_provider, precision_not_applicable
    )

    return (
        "## Medication Detection\n\n"
        "**End-to-end** counts every attempted case; a response that never parsed as valid, "
        "schema-conforming JSON is scored as an empty prediction (real false negatives against "
        "whatever medications were actually expected), never excluded and never repaired. This is "
        "the only medication-detection view shown for a provider with zero evaluable cases."
        f"{precision_note}"
        f"{macro_f1_note}\n\n"
        f"{end_to_end_table}"
        f"{conditional_section}\n\n"
        "![Medication detection](figures/medication_detection.svg)"
    )


def _render_attributes(provider_order: list[str], sources: dict[str, ProviderSource]) -> str:
    sections = []
    for provider in provider_order:
        source = sources[provider]
        if _evaluable_count(source) == 0:
            sections.append(f"**{provider}**: not applicable, 0 evaluable cases.")
            continue

        attributes = source.provider_metrics["attributes"]
        rows = [
            [
                field,
                str(attributes[field]["matched_pairs"]),
                _pct(attributes[field]["accuracy"]),
                _pct(attributes[field]["accuracy_given_expected_non_null"]),
                _pct(attributes[field]["hallucination_rate_given_expected_null"]),
            ]
            for field in ATTRIBUTE_FIELDS
        ]
        table = _md_table(
            [
                "Field",
                "Matched pairs",
                "Accuracy",
                "Accuracy (expected non-null)",
                "Hallucination rate (expected null)",
            ],
            rows,
        )
        sections.append(f"**{provider}**\n\n{table}")

    return (
        "## Attribute Performance\n\n"
        "Normalized-exact comparison only (whitespace/casing, no semantic normalization; see "
        "benchmark/README.md). Computed only over matched medication pairs from schema-valid "
        "responses, so a provider with 0 evaluable cases has 0 matched pairs and is reported as "
        'not applicable, never as 0% accuracy, since that would misreport "no data" as "every '
        'answer was wrong."\n\n' + "\n\n".join(sections)
    )


def _render_group_breakdown(
    provider_order: list[str],
    sources: dict[str, ProviderSource],
    figures: dict[str, str],
    key: str,
) -> str:
    group_data_by_provider = {
        provider: sources[provider].provider_metrics[key] for provider in provider_order
    }
    groups = sorted({group for data in group_data_by_provider.values() for group in data})

    zero_evaluable = frozenset(
        provider for provider in provider_order if _zero_evaluable_cases(sources[provider])
    )

    rows = []
    for group in groups:
        row = [group]
        for provider in provider_order:
            if provider in zero_evaluable:
                row.append("not applicable")
                continue
            entry = group_data_by_provider[provider].get(group)
            if entry is None:
                row.append("-")
            else:
                row.append(f"{_pct(entry['micro']['f1'])} (n={entry['n']})")
        rows.append(row)

    table = _md_table(["Group", *provider_order], rows)

    label = "Difficulty" if key == "by_difficulty" else "Tag"
    filename = f"{key}.svg"
    figures[filename] = charts.group_breakdown_chart(
        f"F1 by {label.lower()} (end-to-end, micro)",
        provider_order,
        groups,
        group_data_by_provider,
        not_applicable_providers=zero_evaluable,
    )

    tag_note = (
        "\n\nA case can carry more than one tag, so `n` values do not sum to the total case count. "
        "Small groups (as few as 2 cases) are shown in full, never suppressed; always read `n` "
        "alongside the score."
        if key == "by_tag"
        else ""
    )

    zero_evaluable_note = ""
    if zero_evaluable:
        zero_evaluable_note = (
            '\n\nEvery cell is reported as "not applicable" for '
            + ", ".join(sorted(zero_evaluable))
            + f": #90's own per-{label.lower()} scoring gives a vacuous 100% to a group made up "
            "entirely of zero-expected-medication cases, whether or not the provider produced "
            "any real structured output, so a real numeric cell here would risk being read as "
            "genuine performance for a provider that had none to show."
        )

    return (
        f"## {label} Breakdown\n\n"
        f"End-to-end micro F1 (the same interpretation as the headline numbers above), grouped by "
        f"{label.lower()}. `n` is always shown so a group's numbers are never read as more "
        f"statistically meaningful than the sample size actually supports."
        f"{tag_note}{zero_evaluable_note}\n\n"
        f"{table}\n\n"
        f"![{label} breakdown](figures/{filename})"
    )


def _render_latency(
    provider_order: list[str], sources: dict[str, ProviderSource], figures: dict[str, str]
) -> str:
    latency_by_provider = {
        provider: sources[provider].provider_metrics["latency_ms"] for provider in provider_order
    }
    rows = [
        [
            provider,
            str(latency_by_provider[provider]["count"]),
            f"{latency_by_provider[provider]['median']:.0f}",
            f"{latency_by_provider[provider]['p95']:.0f}",
        ]
        for provider in provider_order
    ]
    table = _md_table(["Provider", "Successful calls", "Median (ms)", "p95 (ms)"], rows)

    figures["latency.svg"] = charts.latency_chart(provider_order, latency_by_provider)

    return (
        "## Latency\n\n"
        "**Not a hardware-comparable measurement.** Gemini's latency reflects a hosted API call; "
        "OpenBioLLM's and MedGemma's reflect local Ollama inference on whichever machine executed "
        "this benchmark run. A faster or slower number here says nothing about either provider's "
        "architecture or intrinsic speed; it only reflects this specific run's own network "
        "conditions (for Gemini) or local hardware (for OpenBioLLM/MedGemma). Computed only over "
        "successful calls (see benchmark/README.md).\n\n"
        f"{table}\n\n"
        "![Latency](figures/latency.svg)"
    )


def _render_qualitative(
    provider_order: list[str], qualitative_by_provider: dict[str, QualitativeFindings]
) -> str:
    sections = []
    for provider in provider_order:
        findings = qualitative_by_provider[provider]
        parts = [f"### {provider}"]

        if findings.schema_valid_count == 0:
            parts.append(
                "No schema-valid responses: there is no structured `possible_inconsistencies` or "
                "`summary` output to excerpt for this provider."
            )
            if findings.raw_response_examples:
                parts.append(
                    "Shown below **for illustration only, not scored**: a small sample of this "
                    "provider's raw, unparsed responses."
                )
                for example in findings.raw_response_examples:
                    parts.append(f"- **{example.case_id}** (raw, unparsed):\n  > {example.provider_response}")
            sections.append("\n\n".join(parts))
            continue

        parts.append(
            f"{findings.non_empty_inconsistency_count} of {findings.schema_valid_count} "
            "schema-valid responses included a non-empty `possible_inconsistencies` list. "
            "**This is a raw frequency count of output behavior, not an accuracy, recall, or "
            "sensitivity metric**, because #90 defines no ground truth for which cases *should* "
            "have produced a flagged inconsistency, so this number cannot and does not say "
            "whether flagging was correct."
        )

        if findings.inconsistency_examples:
            parts.append("Example `possible_inconsistencies` output (illustrative, not scored):")
            for example in findings.inconsistency_examples:
                bullet_list = "\n".join(f"  - {item}" for item in example.possible_inconsistencies)
                parts.append(f"- **{example.case_id}**:\n{bullet_list}")

        if findings.summary_examples:
            parts.append(
                "Example `summary` output (illustrative only, **not ranked or compared for "
                "quality** across providers):"
            )
            for example in findings.summary_examples:
                parts.append(f"- **{example.case_id}**: {example.summary}")

        sections.append("\n\n".join(parts))

    return (
        "## Qualitative Discussion: possible_inconsistencies and summary\n\n"
        "Issue #90 deliberately excludes both fields from quantitative scoring, since there is no "
        "ground-truth annotation in this benchmark for what an ideal `possible_inconsistencies` "
        "list or `summary` should contain, so no accuracy/recall/quality metric is computed for "
        "either, and none is implied by anything below.\n\n" + "\n\n".join(sections)
    )


def _render_zero_evaluable_notes(provider_order: list[str], sources: dict[str, ProviderSource]) -> str:
    notes = []
    for provider in provider_order:
        if _evaluable_count(sources[provider]) == 0:
            note = _ZERO_EVALUABLE_PROVIDER_NOTES.get(provider, _GENERIC_ZERO_EVALUABLE_NOTE)
            notes.append(f"### {provider}\n\n{note}")

    if not notes:
        return ""

    return "## Notes on Providers with Zero Evaluable Cases\n\n" + "\n\n".join(notes)


def _render_limitations() -> str:
    return (
        "## Limitations\n\n"
        "- **30 synthetic cases.** This benchmark is hand-written and synthetic (see "
        "docs/design-decisions.md's Decision 8); it is not a large-scale or randomly sampled "
        "evaluation, and no result here should be read as a precise population estimate.\n"
        "- **Exact-match-oriented scoring.** Attribute comparison is normalized-exact only "
        "(whitespace/casing), with no semantic or alias normalization beyond the fixed medication-"
        "name matching rules in benchmark/metrics/matching.py; a correct answer phrased differently "
        "than the ground truth is scored as incorrect.\n"
        "- **Quantized local models vs. a hosted API.** OpenBioLLM and MedGemma run as Q4_K_M "
        "GGUF quantizations on local hardware; Gemini is a hosted API with provider-controlled "
        "serving configuration (its serving precision and hardware are not known to this "
        "project). Any quality difference may partly reflect quantization, not only the "
        "underlying model.\n"
        "- **No statistical significance testing.** No confidence intervals, hypothesis tests, or "
        "significance claims are computed anywhere in this report; with 30 cases and no repeated "
        "trials, none would be meaningful.\n"
        "- **Medication-reconciliation-focused, not a general clinical-capability benchmark.** "
        "This benchmark measures structured medication extraction from clinical notes only; it "
        "makes no claim about any provider's broader clinical reasoning, diagnostic, or general "
        "medical-knowledge capability."
    )


def _render_appendix(
    provider_order: list[str], sources: dict[str, ProviderSource], cli_invocation: str
) -> str:
    run_lines = "\n".join(
        f"- **{provider}**: `benchmark/results/{sources[provider].run_id}/`" for provider in provider_order
    )
    return (
        "## Appendix: Reproducing This Report\n\n"
        f"```\n{cli_invocation}\n```\n\n"
        "Source run artifacts (unmodified by this report):\n\n"
        f"{run_lines}"
    )
