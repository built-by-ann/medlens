"""Developer CLI for the evaluation metrics scorer (Issue #90):

    python -m benchmark.metrics benchmark/results/<run-id>

See benchmark/README.md for full usage/methodology. Scores an already-
completed benchmark/runner (Issue #89) run: reads its manifest.json/
predictions.jsonl, verifies the run is complete and the benchmark
dataset hasn't changed since, computes every metric in scoring.py, and
writes metrics.json into the same run directory. Never constructs or
calls an AIProvider, and never reruns anything; this is a pure scoring
step over artifacts #89 already produced.
"""

from __future__ import annotations

import argparse
import sys
from datetime import UTC, datetime
from pathlib import Path

from benchmark.loader import load_cases
from benchmark.metrics.io import (
    RunIntegrityError,
    check_every_provider_has_predictions,
    check_fingerprint,
    check_known_cases,
    check_metrics_not_already_written,
    check_no_duplicate_records,
    check_status,
    read_manifest,
    read_predictions,
    write_metrics,
)
from benchmark.metrics.scoring import (
    ATTRIBUTE_FIELDS,
    score_attribute,
    score_by_difficulty,
    score_by_tag,
    score_latency,
    score_medication_detection,
    score_notes,
    score_reliability,
    score_source_note,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m benchmark.metrics",
        description=(
            "Scores an existing benchmark/runner (Issue #89) evaluation run and writes "
            "metrics.json alongside its manifest.json/predictions.jsonl. Never calls an AI "
            "provider or reruns anything. Computes no ranking, comparison, or human-facing "
            "report of its own - see Issue #91."
        ),
    )
    parser.add_argument(
        "run_dir", type=Path, help="Path to an existing benchmark/results/<run-id>/ directory."
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Score a run whose manifest status isn't 'complete' (e.g. 'interrupted').",
    )
    parser.add_argument(
        "--allow-fingerprint-mismatch",
        action="store_true",
        help="Score even if the benchmark dataset has changed since the run was executed.",
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite an existing metrics.json in run_dir."
    )
    return parser


def _utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    run_dir: Path = args.run_dir

    try:
        manifest = read_manifest(run_dir)
        check_metrics_not_already_written(run_dir, args.force)
        check_status(manifest, args.allow_incomplete)

        cases = load_cases()
        cases_by_id = {case.case_id: case for case in cases}
        mismatched_fingerprint = check_fingerprint(manifest, cases, args.allow_fingerprint_mismatch)

        records = read_predictions(run_dir)
        check_no_duplicate_records(records)
        check_known_cases(records, cases_by_id)
        check_every_provider_has_predictions(manifest, records)
    except RunIntegrityError as error:
        print(str(error), file=sys.stderr)
        return 1

    providers: dict[str, dict] = {}
    for provider_name in manifest["selected_providers"]:
        provider_records = [record for record in records if record["provider"] == provider_name]
        detection, matched_pairs = score_medication_detection(cases_by_id, provider_records)

        attributes = {field: score_attribute(matched_pairs, field) for field in ATTRIBUTE_FIELDS}
        attributes["notes"] = score_notes(matched_pairs)
        attributes["source_note"] = score_source_note(matched_pairs)

        providers[provider_name] = {
            "reliability": score_reliability(provider_records),
            "medication_detection": detection,
            "attributes": attributes,
            "latency_ms": score_latency(provider_records),
            "by_difficulty": score_by_difficulty(cases_by_id, provider_records),
            "by_tag": score_by_tag(cases_by_id, provider_records),
        }

    metrics = {
        "run_id": manifest["run_id"],
        "scored_at": _utc_now_iso(),
        "benchmark_fingerprint": manifest["benchmark_fingerprint"],
        "case_count": manifest["case_count"],
        "run_status": manifest["status"],
        "partial": manifest["status"] != "complete",
        "fingerprint_mismatch": (
            {"recomputed_fingerprint": mismatched_fingerprint} if mismatched_fingerprint else None
        ),
        "overrides": {
            "allow_incomplete": args.allow_incomplete,
            "allow_fingerprint_mismatch": args.allow_fingerprint_mismatch,
            "force": args.force,
        },
        "providers": providers,
    }
    write_metrics(run_dir, metrics)

    print(f"Wrote metrics.json to {run_dir}")
    return 0
