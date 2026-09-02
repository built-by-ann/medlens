"""Shared presentation settings for the comparison report's charts (Issue
#91 visual redesign). Every visual decision common to more than one chart
lives here exactly once: the provider color mapping, the heatmap's
magnitude colormap, typography, spacing, and the tag-identifier display
formatter. `benchmark/report/chart_data.py` (pure data-to-spec logic) and
`benchmark/report/charts.py` (matplotlib rendering) both depend on this
module; neither duplicates a color, font size, or margin value of its own.

Deliberately no bundled font file and no SVG-text-to-path conversion:
`svg.fonttype = "none"` keeps every chart's text as real, selectable SVG
`<text>` elements, and the font stack below is a widely-available sans-
serif fallback chain, not a reproducibility requirement pinned to one
exact typeface. Exact glyph rendering may differ slightly across the
machine that generates a chart and the browser that displays it; the data
itself, layout, and color mapping do not.
"""

from __future__ import annotations

from matplotlib.colors import LinearSegmentedColormap

# --- Provider identity -------------------------------------------------
#
# Okabe-Ito, the standard colorblind-safe qualitative palette (Okabe &
# Ito, "Color Universal Design," 2008), reordered so the first three
# entries are visually distinct from one another at a glance and none of
# them read as a plain primary red/green/blue. Assigned by citation
# order (build_provider_colors, below), never by provider name, so a
# report citing a different set of providers still gets a consistent,
# deterministic mapping.
PROVIDER_PALETTE: tuple[str, ...] = (
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#009E73",  # bluish green
    "#CC79A7",  # reddish purple
    "#E69F00",  # orange
)

# Display-only names for the three providers this evaluation currently
# cites, keyed by the internal identifier every metrics.json/predictions
# lookup still uses unchanged. A provider not in this map falls back to a
# simple capitalized form (humanize_provider, below) rather than raising,
# so a report citing a provider this map doesn't yet know about still
# renders something reasonable.
PROVIDER_DISPLAY_NAMES: dict[str, str] = {
    "gemini": "Gemini",
    "openbiollm": "OpenBioLLM",
    "medgemma": "MedGemma",
}

# Used for a value this report deliberately does not plot as a number
# (a provider with zero evaluable cases): a muted, unambiguous "N/A"
# label, never a color from PROVIDER_PALETTE, and never a bar/dot at
# height or position zero, since the whole point is that this is not the
# same thing as an observed 0%.
NOT_APPLICABLE_LABEL = "N/A"
NOT_APPLICABLE_COLOR = "#9A9A94"
# A visible pill/badge background behind a per-cell "N/A" label (see
# charts.py's render_dotplot), so it reads as a deliberate, bounded
# marker rather than stray floating text that could be mistaken for an
# unlabeled data point.
NOT_APPLICABLE_BADGE_FACE = "#E9E9E3"

# --- Neutral palette -----------------------------------------------------

BACKGROUND = "#FAFAF7"  # fixed, very light off-white; never transparent
INK = "#2B2B28"  # primary text/label color, softer than pure black
MUTED_INK = "#6B6B65"  # secondary text: subtitles, annotations, n counts
GRID = "#DDDDD6"  # gridlines, kept subtle and used only where useful
SPINE = "#C7C7BE"  # the one retained axis line per chart, if any

# A single-hue sequential ramp for the reliability heatmap's cell
# magnitude (0-100%), independent of PROVIDER_PALETTE on purpose: cell
# color encodes a percentage, not a provider identity, and reusing a
# provider's own color for that would conflate the two.
HEATMAP_CMAP = LinearSegmentedColormap.from_list(
    "medlens_heatmap", ["#EFEFEA", "#1F3A44"], N=256
)

# --- Typography ----------------------------------------------------------

FONT_FAMILY = (
    "Helvetica Neue",
    "Helvetica",
    "Arial",
    "Liberation Sans",
    "DejaVu Sans",
    "sans-serif",
)

TITLE_SIZE = 12
AXIS_LABEL_SIZE = 9.5
TICK_LABEL_SIZE = 9
VALUE_LABEL_SIZE = 9
ANNOTATION_SIZE = 8.5
LEGEND_SIZE = 9


def apply_global_style() -> None:
    """Sets the matplotlib rcParams every chart in this package shares.
    Idempotent and cheap; called once at import time by charts.py rather
    than duplicated per chart function.
    """
    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "svg.fonttype": "none",  # real, selectable SVG text, never paths
            "font.family": "sans-serif",
            "font.sans-serif": list(FONT_FAMILY),
            "text.color": INK,
            "axes.edgecolor": SPINE,
            "axes.labelcolor": INK,
            "axes.titlecolor": INK,
            "axes.facecolor": BACKGROUND,
            "figure.facecolor": BACKGROUND,
            "savefig.facecolor": BACKGROUND,
            "xtick.color": MUTED_INK,
            "ytick.color": INK,
            "grid.color": GRID,
            "grid.linewidth": 0.8,
            "axes.grid": False,  # enabled per-axis, only where it helps
            "font.size": TICK_LABEL_SIZE,
        }
    )


def build_provider_colors(provider_order: list[str]) -> dict[str, str]:
    """One color per cited provider, assigned by citation order and
    memoized by the caller for the lifetime of one report so every chart
    that plots the same provider uses the identical color (see
    render.py's render_report, which builds this once and threads it
    through every chart-rendering call).
    """
    return {
        provider: PROVIDER_PALETTE[index % len(PROVIDER_PALETTE)]
        for index, provider in enumerate(provider_order)
    }


def humanize_provider(provider: str) -> str:
    """Display-only provider name, e.g. "openbiollm" -> "OpenBioLLM".
    Never changes, stores, or is used as the underlying identifier
    itself: every metrics/color/legend-ordering lookup keyed by provider
    still uses the raw identifier unchanged; this function's return
    value is only ever put in front of a reader (chart legends, axis
    labels, annotations). A provider not in PROVIDER_DISPLAY_NAMES falls
    back to a plain capitalized form rather than raising, so a report
    citing an unfamiliar provider still renders something reasonable.
    """
    return PROVIDER_DISPLAY_NAMES.get(provider, provider.capitalize())


def humanize_tag(tag_id: str) -> str:
    """Display-only formatting for a benchmark tag identifier, e.g.
    "conflicting_across_documents" -> "Conflicting across documents".
    Never changes, stores, or is used as the underlying identifier
    itself: every lookup into a metrics dict keyed by tag still uses
    `tag_id` unchanged; this function's return value is only ever put in
    front of a reader. A purely mechanical transform (never a per-tag
    lookup table), so it can never drift out of sync with
    `benchmark/loader.py`'s actual KNOWN_TAGS vocabulary; a newly added
    tag is humanized correctly with no change needed here. Known,
    accepted cosmetic limitation: an abbreviation tag like "prn" becomes
    "Prn" rather than "PRN", since this function has no notion of which
    words are abbreviations without a hand-maintained exception list,
    which would reintroduce the exact per-tag drift risk this design
    avoids.
    """
    return tag_id.replace("_", " ").capitalize()
