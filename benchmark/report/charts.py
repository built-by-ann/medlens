"""Pure-function SVG chart generation for the comparison report (Issue
#91). No plotting library and no new dependency, matching every provider
integration in this codebase, which reaches for the stdlib first (see
docs/ai.md's Ollama migration). Every function here takes already-scored
values (never predictions.jsonl, never re-derives a metric #90 already
computed) and returns a self-contained SVG string with no external
references, safe to write to a standalone .svg file.

Kept deliberately simple: fixed margins, a handful of grouped-bar chart
shapes, no animation, no interactivity. `_bar_height`/`_grouped_bar_chart`
are the only real drawing logic; every public chart function is a thin,
labeled call into `_grouped_bar_chart`, which is what keeps them testable
by asserting on structure (bar count, computed height) rather than by
comparing rendered pixels.
"""

from __future__ import annotations

# A small, fixed, deterministic palette, reused by index and never
# reassigned per run, so the same series always gets the same color
# across reports (e.g. "Precision" is always the first color).
_PALETTE = ("#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed", "#0891b2")

_MARGIN_LEFT = 56
_MARGIN_RIGHT = 24
_MARGIN_TOP = 48
_MARGIN_BOTTOM = 64
_BAR_GAP_RATIO = 0.25  # fraction of each bar's own width left as a gap


def _bar_height(value: float, y_max: float, plot_height: float) -> float:
    """Pure function, tested directly: a bar's pixel height for `value`
    against an axis topping out at y_max. Clamped to the plot area even
    if a value is (legitimately, e.g. a rate) never expected to exceed
    y_max, so a bad input never draws outside the chart.
    """
    if y_max <= 0:
        return 0.0
    fraction = max(0.0, min(value / y_max, 1.0))
    return fraction * plot_height


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _grouped_bar_chart(
    *,
    title: str,
    categories: list[str],
    series: list[tuple[str, list[float | None]]],
    y_max: float,
    value_format: str,
    width: int = 720,
    height: int = 360,
    caption: str | None = None,
) -> str:
    """categories: the x-axis groups (e.g. providers, or difficulty/tag
    names). series: [(label, [one value per category]), ...], and every
    series list must be the same length as `categories`. Renders one
    cluster of len(series) bars per category. A value of None renders as
    a zero-height bar labeled "N/A", meaning "not applicable," never a
    real, chartable zero (see medication_detection_chart's precision_not_applicable).
    """
    plot_width = width - _MARGIN_LEFT - _MARGIN_RIGHT
    plot_height = height - _MARGIN_TOP - _MARGIN_BOTTOM
    band_width = plot_width / max(len(categories), 1)
    bar_width = band_width / (len(series) + _BAR_GAP_RATIO * (len(series) + 1))
    gap = bar_width * _BAR_GAP_RATIO

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}" font-family="sans-serif">'
    )
    parts.append(f'<rect x="0" y="0" width="{width}" height="{height}" fill="white"/>')
    parts.append(
        f'<text x="{width / 2:.1f}" y="24" text-anchor="middle" font-size="16" '
        f'font-weight="bold">{_escape(title)}</text>'
    )

    baseline_y = _MARGIN_TOP + plot_height
    parts.append(
        f'<line x1="{_MARGIN_LEFT}" y1="{baseline_y:.1f}" x2="{width - _MARGIN_RIGHT}" '
        f'y2="{baseline_y:.1f}" stroke="#94a3b8" stroke-width="1"/>'
    )

    # Legend, one swatch per series, left to right under the title.
    legend_x = _MARGIN_LEFT
    for series_index, (label, _values) in enumerate(series):
        color = _PALETTE[series_index % len(_PALETTE)]
        parts.append(f'<rect x="{legend_x}" y="32" width="10" height="10" fill="{color}"/>')
        parts.append(
            f'<text x="{legend_x + 14}" y="41" font-size="11">{_escape(label)}</text>'
        )
        legend_x += 14 + 8 * len(label) + 16

    for category_index, category in enumerate(categories):
        band_x = _MARGIN_LEFT + category_index * band_width
        for series_index, (_label, values) in enumerate(series):
            value = values[category_index]
            # None means "not applicable" (see medication_detection_chart's
            # precision_not_applicable), never a real, chartable 0; it is
            # drawn as a zero-height bar labeled "N/A", never a misleading
            # full or partial bar.
            bar_h = 0.0 if value is None else _bar_height(value, y_max, plot_height)
            bar_x = band_x + gap + series_index * (bar_width + gap)
            bar_y = baseline_y - bar_h
            color = _PALETTE[series_index % len(_PALETTE)]
            parts.append(
                f'<rect x="{bar_x:.1f}" y="{bar_y:.1f}" width="{bar_width:.1f}" '
                f'height="{bar_h:.1f}" fill="{color}"/>'
            )
            label_text = "N/A" if value is None else value_format.format(value)
            parts.append(
                f'<text x="{bar_x + bar_width / 2:.1f}" y="{bar_y - 4:.1f}" '
                f'text-anchor="middle" font-size="10">{_escape(label_text)}</text>'
            )

        parts.append(
            f'<text x="{band_x + band_width / 2:.1f}" y="{baseline_y + 18:.1f}" '
            f'text-anchor="middle" font-size="11">{_escape(category)}</text>'
        )

    if caption:
        parts.append(
            f'<text x="{width / 2:.1f}" y="{height - 8}" text-anchor="middle" '
            f'font-size="10" fill="#64748b">{_escape(caption)}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def medication_detection_chart(
    providers: list[str],
    detection_by_provider: dict[str, dict],
    precision_not_applicable: frozenset[str] = frozenset(),
) -> str:
    """End_to_end micro precision/recall/F1 per provider, always shown
    for every cited provider, including one with zero evaluable cases:
    end_to_end already treats an unparseable response as an empty
    prediction (see scoring.py's _detection_over), so recall/F1 are never
    vacuous or undefined, unlike conditional_on_valid_output.

    Precision is the one exception: #90's own precision_recall_f1 reports
    a mathematically-conventional 1.0 when nothing was predicted at all
    (TP=0, FP=0, vacuously precise), which is correct scoring
    methodology but misleading as a human-facing chart bar for a
    provider with zero evaluable cases and zero predicted positives (it
    would read as "100% precision," not "predicted nothing, ever").
    `precision_not_applicable` names providers render.py has determined
    meet that exact condition; their precision bar renders as "N/A", not
    a full bar. #90's own stored metric is never changed; only this
    chart's display of it is.
    """
    series = [
        (
            metric_label,
            [
                None if (metric_key == "precision" and provider in precision_not_applicable)
                else detection_by_provider[provider]["end_to_end"]["micro"][metric_key]
                for provider in providers
            ],
        )
        for metric_label, metric_key in (
            ("Precision", "precision"),
            ("Recall", "recall"),
            ("F1", "f1"),
        )
    ]
    return _grouped_bar_chart(
        title="Medication Detection (end-to-end, micro)",
        categories=providers,
        series=series,
        y_max=1.0,
        value_format="{:.0%}",
        caption="Every attempted case counts; an unparseable response scores as an empty prediction.",
    )


def reliability_chart(providers: list[str], reliability_by_provider: dict[str, dict]) -> str:
    """Grouped bars, one cluster of 4 per provider: call success, JSON
    validity, schema validity, evaluable case rate. A grouped
    comparison rather than a funnel, so a provider whose calls all
    succeed but never produce valid structured output (e.g. OpenBioLLM:
    100% success, 0% on the remaining three) is immediately visible as
    one full bar next to three flat ones, not hidden inside a single
    collapsing funnel shape.
    """
    series = [
        (
            rate_label,
            [reliability_by_provider[provider][rate_key] for provider in providers],
        )
        for rate_label, rate_key in (
            ("Provider call success", "provider_call_success_rate"),
            ("JSON validity", "json_validity_rate"),
            ("Schema validity", "schema_validity_rate"),
            ("Evaluable case rate", "evaluable_case_rate"),
        )
    ]
    return _grouped_bar_chart(
        title="Reliability",
        categories=providers,
        series=series,
        y_max=1.0,
        value_format="{:.0%}",
        caption="JSON/schema validity rates are computed over successful calls only (see benchmark/README.md).",
    )


def latency_chart(providers: list[str], latency_by_provider: dict[str, dict]) -> str:
    """Median and p95 latency per provider, over successful calls only
    (matching score_latency's own population). Always captioned as not
    hardware-comparable: local providers run on whatever machine executed
    the benchmark, never a controlled/shared environment the way a
    hosted API's latency at least approximates.
    """
    values = [latency_by_provider[provider] for provider in providers]
    series = [
        ("Median (ms)", [v["median"] for v in values]),
        ("p95 (ms)", [v["p95"] for v in values]),
    ]
    y_max = max((v["p95"] for v in values), default=0.0) * 1.15 or 1.0
    return _grouped_bar_chart(
        title="Latency (API vs. local; not hardware-comparable)",
        categories=providers,
        series=series,
        y_max=y_max,
        value_format="{:.0f}",
        caption=(
            "Local providers ran on the evaluation machine's own hardware; Gemini's latency is a "
            "hosted API call. These are not a controlled, apples-to-apples comparison."
        ),
    )


def group_breakdown_chart(
    title: str,
    providers: list[str],
    groups: list[str],
    f1_by_provider_and_group: dict[str, dict],
    not_applicable_providers: frozenset[str] = frozenset(),
) -> str:
    """by_difficulty / by_tag: one cluster per group (difficulty level, or
    tag), one bar per provider, F1 only (end_to_end interpretation, the
    same one by_difficulty/by_tag themselves use; see scoring.py). Used
    for both breakdowns via a different `groups`/title; the value lookup
    quietly defaults to 0.0 for a (provider, group) pair the group didn't
    include any cases for, rather than raising, since by_tag groups in
    particular are not guaranteed to include every provider's full case
    set identically only when case sets already matched (validation.py
    already enforces this, so in practice every provider has every group
    a shared case touches).

    `not_applicable_providers` names providers render.py has determined
    produced zero evaluable cases: every one of that provider's bars
    renders as "N/A" across every group, never a real F1 value. A group
    made up entirely of zero-expected-medication cases scores a vacuous
    100% under #90's own conventions regardless of whether the provider
    produced any real output, so without this override such a provider
    could appear to "score" perfectly on a group despite having no
    evaluable output at all.
    """
    series = [
        (
            provider,
            [None] * len(groups)
            if provider in not_applicable_providers
            else [
                f1_by_provider_and_group[provider].get(group, {}).get("micro", {}).get("f1", 0.0)
                for group in groups
            ],
        )
        for provider in providers
    ]
    return _grouped_bar_chart(
        title=title,
        categories=groups,
        series=series,
        y_max=1.0,
        value_format="{:.0%}",
        width=max(720, 90 * len(groups)),
    )
