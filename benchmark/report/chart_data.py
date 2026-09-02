"""Pure data-to-chart-specification logic for the comparison report's
charts (Issue #91 visual redesign). Nothing in this module imports
matplotlib, opens a file, or reads predictions.jsonl; every function
takes plain dicts already read from a provider's own metrics.json (the
same `provider_metrics`/`reliability_by_provider`/etc. shapes render.py
already builds) and returns a small, frozen dataclass describing exactly
what a chart should show; no more, no less.

This is deliberately the layer render_data-shape decisions (row order,
which cells are "not applicable", label text, provider-color-independent
ordering) live in and get thoroughly unit-tested in, separately from
`benchmark/report/charts.py`'s matplotlib rendering, which only ever
turns an already-decided spec into pixels/paths. See
backend/tests/test_evaluation_report.py's "chart_data.py" section.

A value of `None` in any spec means "not applicable": a provider with
zero evaluable cases, never a real, chartable 0. This sentinel is never
constructed from a genuinely-zero metric; see each builder's own
docstring for exactly which condition produces it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from benchmark.report import chart_style

# Natural reading order for the difficulty dot plot, deliberately not
# alphabetical (unlike the tag table/chart, which stays identifier-
# alphabetical by explicit request). The Difficulty Breakdown *table*
# keeps its own existing alphabetical order; only this chart uses this
# ordering.
DIFFICULTY_ORDER: tuple[str, ...] = ("easy", "medium", "hard")

RELIABILITY_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("Call success", "provider_call_success_rate", "% of attempted"),
    ("JSON validity", "json_validity_rate", "% of successful calls"),
    ("Schema validity", "schema_validity_rate", "% of valid JSON"),
    ("Evaluable cases", "evaluable_case_rate", "% of attempted"),
)


@dataclass(frozen=True)
class HeatmapSpec:
    providers: list[str]
    columns: list[str]
    column_subtitles: list[str]
    # providers x columns, already on a 0-100 scale; never None, since
    # every reliability rate is always a real, defined number (see
    # scoring.py's score_reliability: each rate's own when_zero default
    # makes this always a real 0.0-100.0 value).
    values: list[list[float]]


@dataclass(frozen=True)
class DotPlotRow:
    label: str
    # provider -> percentage (0-100), or None for "not applicable" *for
    # this one cell* (the provider is still plotted elsewhere; see
    # DotPlotSpec.providers). A provider named in DotPlotSpec's own
    # omitted_providers is never a key here at all - see that field's
    # own docstring for the distinction.
    values: dict[str, float | None]


@dataclass(frozen=True)
class DotPlotSpec:
    rows: list[DotPlotRow]
    # Providers actually plotted as dots/legend entries in this chart.
    providers: list[str]
    # Providers not plotted anywhere in this chart at all (e.g. every
    # row would otherwise be "not applicable" for them) - named once,
    # for a single chart-level annotation, rather than a per-cell None
    # in every row. Distinct from a per-cell None in DotPlotRow.values,
    # which marks one specific cell as not applicable for a provider
    # that IS otherwise plotted (see
    # build_medication_detection_dotplot_spec vs.
    # build_difficulty_dotplot_spec, below, for one of each).
    omitted_providers: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DumbbellRow:
    tag_id: str  # the real, unmodified benchmark tag identifier
    display_label: str  # humanized text plus its sample size, display-only
    # provider -> percentage (0-100); only ever contains plotted
    # (evaluable) providers. An omitted provider has no key here at all,
    # never a None placeholder, since DumbbellSpec.omitted_providers
    # already names it once for the whole chart.
    values: dict[str, float]


@dataclass(frozen=True)
class DumbbellSpec:
    rows: list[DumbbellRow]
    plotted_providers: list[str]
    omitted_providers: list[str]


@dataclass(frozen=True)
class LatencyRow:
    provider: str
    median: float
    p95: float


@dataclass(frozen=True)
class LatencySpec:
    rows: list[LatencyRow]


def build_reliability_heatmap_spec(
    provider_order: list[str], reliability_by_provider: dict[str, dict]
) -> HeatmapSpec:
    columns = [label for label, _key, _subtitle in RELIABILITY_COLUMNS]
    subtitles = [subtitle for _label, _key, subtitle in RELIABILITY_COLUMNS]
    values = [
        [reliability_by_provider[provider][key] * 100 for _label, key, _subtitle in RELIABILITY_COLUMNS]
        for provider in provider_order
    ]
    return HeatmapSpec(
        providers=list(provider_order), columns=columns, column_subtitles=subtitles, values=values
    )


def build_medication_detection_dotplot_spec(
    provider_order: list[str],
    detection_by_provider: dict[str, dict],
    precision_not_applicable: frozenset[str],
) -> DotPlotSpec:
    """Precision is the only row where "not applicable" can appear -
    end-to-end recall/F1 are always real, defined numbers even for a
    zero-evaluable provider (see scoring.py's _detection_over: an
    unparseable response is scored as an empty prediction, a genuine
    false negative, not an undefined value). `precision_not_applicable`
    is computed by render.py's own _precision_not_applicable, the single
    source of truth for that condition; this function never re-derives
    it.
    """
    rows = []
    for metric_label, metric_key in (("Precision", "precision"), ("Recall", "recall"), ("F1", "f1")):
        values: dict[str, float | None] = {}
        for provider in provider_order:
            if metric_key == "precision" and provider in precision_not_applicable:
                values[provider] = None
            else:
                values[provider] = (
                    detection_by_provider[provider]["end_to_end"]["micro"][metric_key] * 100
                )
        rows.append(DotPlotRow(label=metric_label, values=values))
    return DotPlotSpec(rows=rows, providers=list(provider_order))


def build_difficulty_dotplot_spec(
    provider_order: list[str],
    group_data_by_provider: dict[str, dict],
    zero_evaluable: frozenset[str],
) -> DotPlotSpec:
    """A zero-evaluable provider is "not applicable" uniformly across
    easy/medium/hard, unlike medication detection, where only the
    precision row is affected. Rather than repeating a "not applicable"
    mark in every row, such a provider is omitted from the plotted rows
    entirely and named once, in DotPlotSpec.omitted_providers, for a
    single chart-level annotation instead (mirroring
    build_tag_dumbbell_spec's identical treatment). `zero_evaluable` is
    computed by render.py's own _zero_evaluable_cases, the single source
    of truth for that condition.
    """
    present_groups = [
        group for group in DIFFICULTY_ORDER if any(group in data for data in group_data_by_provider.values())
    ]
    plotted_providers = [provider for provider in provider_order if provider not in zero_evaluable]
    omitted_providers = [provider for provider in provider_order if provider in zero_evaluable]

    rows = []
    for group in present_groups:
        sample_size = next(
            group_data_by_provider[provider][group]["n"]
            for provider in provider_order
            if group in group_data_by_provider[provider]
        )
        values = {
            provider: group_data_by_provider[provider][group]["micro"]["f1"] * 100
            for provider in plotted_providers
        }
        rows.append(DotPlotRow(label=f"{group.capitalize()} (n={sample_size})", values=values))
    return DotPlotSpec(rows=rows, providers=plotted_providers, omitted_providers=omitted_providers)


def build_tag_dumbbell_spec(
    provider_order: list[str],
    groups: list[str],
    group_data_by_provider: dict[str, dict],
    zero_evaluable: frozenset[str],
) -> DumbbellSpec:
    """`groups` is expected to already be sorted alphabetically by tag
    identifier (render.py's own sort), preserved here unchanged so the
    chart's row order always matches the table's. A zero-evaluable
    provider is omitted from every row entirely, never drawn as 18
    individual "not applicable" marks; DumbbellSpec.omitted_providers
    names it once for the chart's own single annotation instead.
    """
    plotted_providers = [provider for provider in provider_order if provider not in zero_evaluable]
    omitted_providers = [provider for provider in provider_order if provider in zero_evaluable]

    rows = []
    for tag in groups:
        sample_size = next(
            group_data_by_provider[provider][tag]["n"]
            for provider in provider_order
            if tag in group_data_by_provider[provider]
        )
        values = {
            provider: group_data_by_provider[provider][tag]["micro"]["f1"] * 100
            for provider in plotted_providers
            if tag in group_data_by_provider[provider]
        }
        display_label = f"{chart_style.humanize_tag(tag)} (n={sample_size})"
        rows.append(DumbbellRow(tag_id=tag, display_label=display_label, values=values))

    return DumbbellSpec(
        rows=rows, plotted_providers=plotted_providers, omitted_providers=omitted_providers
    )


def build_latency_spec(provider_order: list[str], latency_by_provider: dict[str, dict]) -> LatencySpec:
    rows = [
        LatencyRow(
            provider=provider,
            median=latency_by_provider[provider]["median"],
            p95=latency_by_provider[provider]["p95"],
        )
        for provider in provider_order
    ]
    return LatencySpec(rows=rows)
