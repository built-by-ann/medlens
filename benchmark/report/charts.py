"""Matplotlib rendering for the comparison report's charts (Issue #91
visual redesign). Every function here takes an already-built,
already-decided spec from `benchmark/report/chart_data.py` (never a raw
metrics dict, never predictions.jsonl) and returns a self-contained SVG
string; it makes no decision about what data to show, which cell is "not
applicable," or what order rows appear in; see chart_data.py for all of
that. `benchmark/report/chart_style.py` owns every color, font, and
spacing constant used below; nothing here hardcodes a value chart_style
already defines.

No chart embeds its own title: the surrounding report prose (render.py's
own section headings) already gives every figure its context, so a
second, redundant title inside the SVG itself would only spend vertical
space without adding information.

Uses matplotlib's non-interactive Agg backend (`matplotlib.use("Agg")`,
set before pyplot is imported) since these are static report figures
only; see docs/model-evaluation.md and benchmark/README.md for why no
interactivity is needed. No Kaleido, no browser, no bundled font: see
chart_style.py's own module docstring for the font/reproducibility
tradeoff this deliberately accepts.
"""

from __future__ import annotations

import io

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

from benchmark.report import chart_style  # noqa: E402
from benchmark.report.chart_data import DotPlotSpec, DumbbellSpec, HeatmapSpec, LatencySpec  # noqa: E402

chart_style.apply_global_style()

_DOT_MARKER_SIZE = 46
_DUMBBELL_MARKER_SIZE = 34
_LEGEND_Y_ANCHOR = 1.08  # close above the axes, now that no title sits between them


def _figure_to_svg(fig: "plt.Figure") -> str:
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", bbox_inches="tight", pad_inches=0.22)
    plt.close(fig)
    return buffer.getvalue()


def _strip_spines(ax, keep=()) -> None:
    for side, spine in ax.spines.items():
        spine.set_visible(side in keep)


def _legend(ax, providers: list[str], provider_colors: dict[str, str]) -> None:
    handles = [
        Line2D(
            [],
            [],
            marker="o",
            linestyle="none",
            color=provider_colors[provider],
            markersize=7,
            label=chart_style.humanize_provider(provider),
        )
        for provider in providers
    ]
    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, _LEGEND_Y_ANCHOR),
        ncol=len(providers),
        frameon=False,
        fontsize=chart_style.LEGEND_SIZE,
        handletextpad=0.4,
        columnspacing=1.2,
    )


def render_reliability_heatmap(spec: HeatmapSpec) -> str:
    """Rows = providers, columns = the four reliability rates, each cell
    direct-labeled with its own percentage. Deliberately no colorbar (the
    direct labels already carry the exact value; a colorbar would only
    repeat it) and no line or arrow connecting columns, since these four
    rates each have their own denominator and are not a funnel computed
    from one shared base (see chart_data.RELIABILITY_COLUMNS and
    docs/model-evaluation.md's Reliability Metrics section). Each column
    header carries its own denominator subtitle directly on the chart,
    for the same reason.
    """
    n_rows, n_cols = len(spec.providers), len(spec.columns)
    fig_width = 1.7 + 1.55 * n_cols
    fig_height = 1.3 + 0.72 * n_rows
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    ax.imshow(spec.values, cmap=chart_style.HEATMAP_CMAP, vmin=0, vmax=100, aspect="auto")

    for row in range(n_rows):
        for col in range(n_cols):
            value = spec.values[row][col]
            text_color = chart_style.BACKGROUND if value >= 55 else chart_style.INK
            ax.text(
                col,
                row,
                f"{value:.0f}%",
                ha="center",
                va="center",
                fontsize=chart_style.VALUE_LABEL_SIZE + 1,
                color=text_color,
                fontweight="medium",
            )

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(spec.columns, fontsize=chart_style.AXIS_LABEL_SIZE)
    ax.tick_params(axis="x", length=0)
    for tick_index, subtitle in enumerate(spec.column_subtitles):
        ax.text(
            tick_index,
            -0.72,
            subtitle,
            ha="center",
            va="top",
            fontsize=chart_style.ANNOTATION_SIZE,
            color=chart_style.MUTED_INK,
            style="italic",
        )

    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(
        [chart_style.humanize_provider(provider) for provider in spec.providers],
        fontsize=chart_style.AXIS_LABEL_SIZE,
    )
    ax.tick_params(axis="y", length=0)

    ax.set_xlim(-0.5, n_cols - 0.5)
    ax.set_ylim(n_rows - 0.5, -1.05)  # leaves room for the subtitle row above the top edge
    _strip_spines(ax)
    ax.grid(False)

    fig.tight_layout()
    return _figure_to_svg(fig)


def render_dotplot(spec: DotPlotSpec, provider_colors: dict[str, str]) -> str:
    """One horizontal row per spec row, one dot per plotted provider
    offset within that row's band, direct percentage labels.

    Two distinct "not applicable" treatments, matching chart_data.py's
    own distinction: a per-cell None (a provider that IS plotted
    elsewhere in this chart, e.g. medication detection's precision row)
    renders as a muted "N/A" badge, a filled pill rather than bare
    floating text, so it reads as a deliberate marker and can't be
    mistaken for an unlabeled data point. A provider named in
    spec.omitted_providers (e.g. difficulty's zero-evaluable provider,
    not applicable in literally every row) is never drawn per row at
    all; it gets exactly one small annotation for the whole chart
    instead of a repeated mark in every row.
    """
    providers = spec.providers
    n_rows = len(spec.rows)
    offsets = _row_offsets(len(providers))

    fig_width = 6.4
    fig_height = 0.75 + 0.62 * n_rows
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    for row_index, row in enumerate(spec.rows):
        y = n_rows - 1 - row_index
        for provider, offset in zip(providers, offsets, strict=True):
            value = row.values.get(provider)
            color = provider_colors[provider]
            if value is None:
                ax.text(
                    6,
                    y + offset,
                    chart_style.NOT_APPLICABLE_LABEL,
                    ha="center",
                    va="center",
                    fontsize=chart_style.VALUE_LABEL_SIZE - 0.5,
                    color=chart_style.NOT_APPLICABLE_COLOR,
                    style="italic",
                    zorder=3,
                    bbox={
                        "boxstyle": "round,pad=0.32",
                        "facecolor": chart_style.NOT_APPLICABLE_BADGE_FACE,
                        "edgecolor": "none",
                    },
                )
                continue
            ax.scatter([value], [y + offset], s=_DOT_MARKER_SIZE, color=color, zorder=3, edgecolors="none")
            ax.text(
                value + 2.5,
                y + offset,
                f"{value:.1f}%",
                ha="left",
                va="center",
                fontsize=chart_style.VALUE_LABEL_SIZE,
                color=chart_style.INK,
            )

    ax.set_yticks(range(n_rows))
    ax.set_yticklabels([row.label for row in reversed(spec.rows)], fontsize=chart_style.AXIS_LABEL_SIZE)
    ax.set_ylim(-0.7, n_rows - 0.3)

    ax.set_xlim(-2, 122)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=chart_style.TICK_LABEL_SIZE)
    ax.xaxis.grid(True, color=chart_style.GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    _strip_spines(ax, keep=("bottom",))
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0)

    _legend(ax, providers, provider_colors)

    if spec.omitted_providers:
        omitted = ", ".join(chart_style.humanize_provider(provider) for provider in spec.omitted_providers)
        ax.text(
            1.0,
            -0.14,
            f"{omitted}: N/A (zero evaluable cases)",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=chart_style.ANNOTATION_SIZE,
            color=chart_style.NOT_APPLICABLE_COLOR,
            style="italic",
        )

    fig.tight_layout()
    return _figure_to_svg(fig)


def _dumbbell_marker_positions(
    y: float, provider_values: list[tuple[str, float]]
) -> list[tuple[str, float, float]]:
    """Returns (provider, value, y_position) for each entry. Providers
    whose value ties with another provider in the same row (rounded to
    one decimal place, so a hairline floating-point difference is still
    treated as a tie) are spread with a small, symmetric, deterministic
    vertical offset so both dots remain visually discernible; every
    other provider stays exactly on the row's own y. This never changes
    the plotted value itself, only where its marker is drawn, and never
    affects the connecting line, which always spans the row's own true
    min/max.
    """
    rounded_values = [round(value, 1) for _provider, value in provider_values]
    tie_groups: dict[float, list[int]] = {}
    for index, rounded in enumerate(rounded_values):
        tie_groups.setdefault(rounded, []).append(index)

    y_positions = [y] * len(provider_values)
    for indices in tie_groups.values():
        if len(indices) < 2:
            continue
        tie_offsets = _row_offsets(len(indices))
        for offset, provider_index in zip(tie_offsets, indices, strict=True):
            y_positions[provider_index] = y + offset

    return [
        (provider, value, y_position)
        for (provider, value), y_position in zip(provider_values, y_positions, strict=True)
    ]


def render_tag_dumbbell(spec: DumbbellSpec, provider_colors: dict[str, str]) -> str:
    """One row per tag, a line connecting each plotted provider's F1
    value with a dot at each end; a provider with zero evaluable cases
    across every tag is never drawn as a per-row mark at all (see
    chart_data.build_tag_dumbbell_spec), only named once, here, in a
    single, visually secondary annotation below the plot area rather
    than competing with the legend for attention above it.
    """
    n_rows = len(spec.rows)
    fig_width = 6.8
    fig_height = 1.0 + 0.34 * n_rows
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    for row_index, row in enumerate(spec.rows):
        y = n_rows - 1 - row_index
        provider_values = [(provider, row.values[provider]) for provider in spec.plotted_providers]

        if len(provider_values) >= 2:
            xs = [value for _provider, value in provider_values]
            ax.plot([min(xs), max(xs)], [y, y], color=chart_style.GRID, linewidth=2, zorder=1)

        for provider, value, y_position in _dumbbell_marker_positions(y, provider_values):
            color = provider_colors[provider]
            ax.scatter(
                [value], [y_position], s=_DUMBBELL_MARKER_SIZE, color=color, zorder=3, edgecolors="none"
            )

    fig.canvas.draw()  # needed so tick/label extents below are measurable
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(
        [row.display_label for row in reversed(spec.rows)], fontsize=chart_style.AXIS_LABEL_SIZE
    )
    ax.set_ylim(-0.7, n_rows + 0.35)

    ax.set_xlim(-2, 102)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=chart_style.TICK_LABEL_SIZE)
    ax.xaxis.grid(True, color=chart_style.GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)

    _strip_spines(ax, keep=("bottom",))
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", length=0)

    _legend(ax, spec.plotted_providers, provider_colors)

    if spec.omitted_providers:
        omitted = ", ".join(chart_style.humanize_provider(provider) for provider in spec.omitted_providers)
        ax.text(
            1.0,
            -0.045,
            f"{omitted}: N/A for every tag (zero evaluable cases)",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=chart_style.ANNOTATION_SIZE - 0.5,
            color=chart_style.NOT_APPLICABLE_COLOR,
            style="italic",
        )

    fig.tight_layout()
    return _figure_to_svg(fig)


def render_latency(spec: LatencySpec, provider_colors: dict[str, str]) -> str:
    """One row per provider; median (filled marker) and p95 (hollow
    marker) on a shared millisecond axis, each with a direct value label
    positioned at its own marker's own x-position so the association
    between a marker and its label is never ambiguous. No interpretive
    caption: the report's own prose carries the "not hardware-comparable"
    caveat (see docs/model-evaluation.md's Latency section and
    render.py's Latency prose), so this chart communicates only the
    observed numbers.
    """
    n_rows = len(spec.rows)
    max_value = max((row.p95 for row in spec.rows), default=0.0)
    x_max = max_value * 1.22 or 1.0

    fig_width = 6.4
    fig_height = 1.1 + 0.95 * n_rows
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))

    # Both labels are stacked *above* their own row, at two fixed
    # heights, rather than one above and one below: with rows this close
    # together, a label placed below one row and a label placed above
    # the next row would otherwise land in the same vertical band and
    # collide (a real bug caught during visual review of this chart).
    for row_index, row in enumerate(spec.rows):
        y = n_rows - 1 - row_index
        color = provider_colors[row.provider]
        ax.plot([row.median, row.p95], [y, y], color=chart_style.GRID, linewidth=2, zorder=1)
        ax.scatter([row.median], [y], s=_DOT_MARKER_SIZE, color=color, marker="o", zorder=3)
        ax.scatter(
            [row.p95], [y], s=_DOT_MARKER_SIZE, facecolors="none", edgecolors=color, linewidths=1.6, zorder=3
        )
        ax.text(
            row.median,
            y + 0.30,
            f"median {row.median:,.0f} ms",
            ha="center",
            va="bottom",
            fontsize=chart_style.VALUE_LABEL_SIZE,
            color=color,
        )
        ax.text(
            row.p95,
            y + 0.58,
            f"p95 {row.p95:,.0f} ms",
            ha="center",
            va="bottom",
            fontsize=chart_style.VALUE_LABEL_SIZE,
            color=color,
            alpha=0.75,
        )

    ax.set_yticks(range(n_rows))
    ax.set_yticklabels(
        [chart_style.humanize_provider(row.provider) for row in reversed(spec.rows)],
        fontsize=chart_style.AXIS_LABEL_SIZE,
    )
    ax.set_ylim(-0.6, n_rows - 0.15)

    ax.set_xlim(0, x_max)
    ax.xaxis.set_major_formatter(FuncFormatter(_compact_ms_tick))
    ax.xaxis.grid(True, color=chart_style.GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    ax.set_xlabel("milliseconds", fontsize=chart_style.AXIS_LABEL_SIZE, color=chart_style.MUTED_INK)

    _strip_spines(ax, keep=("bottom",))
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=chart_style.TICK_LABEL_SIZE)

    fig.tight_layout()
    return _figure_to_svg(fig)


def _compact_ms_tick(value: float, _position: int) -> str:
    """0 -> "0", 20000 -> "20k", matching a plain reader's expectation of
    a millisecond axis without every tick spelling out four-plus digits.
    """
    if value == 0:
        return "0"
    return f"{value / 1000:g}k"


def _row_offsets(n_providers: int) -> list[float]:
    """Small, symmetric vertical offsets so up to a handful of providers'
    dots within one row never sit exactly on top of each other. Centered
    on 0 regardless of count, e.g. 1 provider -> [0.0], 3 providers ->
    [-0.22, 0.0, 0.22].
    """
    if n_providers <= 1:
        return [0.0] * n_providers
    step = 0.44 / (n_providers - 1)
    start = -0.22
    return [start + step * index for index in range(n_providers)]
