"""Developer CLI for the model comparison report (Issue #91):

    python -m benchmark.report --provider NAME=RUN_ID [--provider NAME=RUN_ID ...] --output DIR

Builds a human-readable comparison report from one or more already-
completed, already-scored `benchmark.runner`/`benchmark.metrics`
(#89/#90) run directories, one provider cited per run. Never calls an
AIProvider, never reruns anything, never recomputes a #90 metric, and
never modifies any `manifest.json`/`predictions.jsonl`/`metrics.json` it
reads. See benchmark/README.md's "Generating a comparison report"
section for the full workflow, including how to promote a reviewed
report into docs/.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from benchmark.atomic_write import atomic_write_text
from benchmark.report.qualitative import build_qualitative_findings
from benchmark.report.render import render_report
from benchmark.report.sources import (
    DEFAULT_RESULTS_DIR,
    ReportIntegrityError,
    load_all_sources,
    parse_provider_mapping,
)
from benchmark.report.validation import validate_sources

DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m benchmark.report",
        description=(
            "Builds a human-readable model comparison report from one or more already-scored "
            "benchmark.runner/benchmark.metrics run directories, one provider cited per run. "
            "Never calls an AIProvider, never reruns anything, and never recomputes a metric; "
            "see Issue #90. Writes report.md and figures/*.svg into --output; never writes "
            "into docs/."
        ),
    )
    parser.add_argument(
        "--provider",
        action="append",
        required=True,
        metavar="NAME=RUN_ID",
        help=(
            "One provider citation, e.g. --provider gemini=20260901-173743-249636. Repeat once "
            "per provider. RUN_ID is resolved as an existing path first, else as "
            "benchmark/results/RUN_ID."
        ),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=DEFAULT_RESULTS_DIR,
        help="Where a bare RUN_ID is resolved against (default: benchmark/results/).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Directory to write report.md and figures/*.svg into (created if missing).",
    )
    return parser


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    cli_invocation = "python -m benchmark.report " + " ".join(argv if argv is not None else sys.argv[1:])

    try:
        provider_to_run_id = parse_provider_mapping(args.provider)
        sources = load_all_sources(provider_to_run_id, results_dir=args.results_dir)
        provider_order = list(sources.keys())
        warnings = validate_sources(list(sources.values()))
    except ReportIntegrityError as error:
        print(str(error), file=sys.stderr)
        return 1

    qualitative_by_provider = {
        provider: build_qualitative_findings(provider, source.predictions)
        for provider, source in sources.items()
    }

    markdown_text, figures = render_report(
        provider_order=provider_order,
        sources=sources,
        warnings=warnings,
        qualitative_by_provider=qualitative_by_provider,
        generated_at=_utc_now_iso(),
        cli_invocation=cli_invocation,
    )

    output_dir: Path = args.output
    figures_dir = output_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    atomic_write_text(output_dir / "report.md", markdown_text)
    for filename, svg_text in figures.items():
        atomic_write_text(figures_dir / filename, svg_text)

    print(f"Wrote report.md and {len(figures)} figure(s) to {output_dir}")
    return 0
