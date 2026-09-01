"""Reading a completed #89 run and writing metrics.json for it (Issue
#90). Read-only with respect to manifest.json/predictions.jsonl - this
module never calls an AIProvider and never reruns anything; it only
validates and scores what #89 already produced. Every check here is
fail-loud by default: scoring through an integrity problem silently
would make the resulting numbers scientifically misleading, which this
project explicitly chooses not to risk (see benchmark/README.md).
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from benchmark.atomic_write import atomic_write_json
from benchmark.loader import BenchmarkCase
from benchmark.runner.models import benchmark_fingerprint


class RunIntegrityError(Exception):
    """Raised for any condition under which scoring would be scientifically
    misleading unless the caller explicitly opted out via one of cli.py's
    --allow-incomplete/--allow-fingerprint-mismatch/--force flags.
    """


def read_manifest(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "manifest.json"
    if not path.exists():
        raise RunIntegrityError(f"No manifest.json found in {run_dir}")
    return json.loads(path.read_text())


def read_predictions(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "predictions.jsonl"
    if not path.exists():
        raise RunIntegrityError(f"No predictions.jsonl found in {run_dir}")

    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def check_metrics_not_already_written(run_dir: Path, force: bool) -> None:
    path = run_dir / "metrics.json"
    if path.exists() and not force:
        raise RunIntegrityError(
            f"metrics.json already exists in {run_dir} - refusing to overwrite a previous "
            "scoring (pass --force to re-score deliberately)."
        )


def check_status(manifest: dict[str, Any], allow_incomplete: bool) -> None:
    if manifest["status"] != "complete" and not allow_incomplete:
        raise RunIntegrityError(
            f"Run status is {manifest['status']!r}, not 'complete' - refusing to score an "
            "incomplete run (pass --allow-incomplete to score it anyway)."
        )


def check_fingerprint(
    manifest: dict[str, Any], cases: list[BenchmarkCase], allow_mismatch: bool
) -> str | None:
    """Recomputes the benchmark fingerprint from the currently-loaded
    cases and compares it to the one the run itself recorded. Returns the
    recomputed fingerprint if it differs from the recorded one (for
    cli.py to record in metrics.json's fingerprint_mismatch field), or
    None if they match.
    """
    recomputed = benchmark_fingerprint(cases)
    recorded = manifest["benchmark_fingerprint"]
    if recomputed == recorded:
        return None

    if not allow_mismatch:
        raise RunIntegrityError(
            f"Benchmark fingerprint mismatch: this run recorded {recorded!r}, but the "
            f"benchmark dataset currently loads as {recomputed!r} - the dataset has changed "
            "since this run was executed (pass --allow-fingerprint-mismatch to score anyway)."
        )

    return recomputed


def check_no_duplicate_records(records: list[dict[str, Any]]) -> None:
    counts = Counter((record["case_id"], record["provider"]) for record in records)
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    if duplicates:
        raise RunIntegrityError(
            f"predictions.jsonl has duplicate (case_id, provider) record(s): {duplicates}"
        )


def check_known_cases(records: list[dict[str, Any]], cases_by_id: dict[str, BenchmarkCase]) -> None:
    unknown = sorted({record["case_id"] for record in records} - set(cases_by_id))
    if unknown:
        raise RunIntegrityError(
            f"predictions.jsonl references unknown benchmark case id(s): {unknown}"
        )


def check_every_provider_has_predictions(
    manifest: dict[str, Any], records: list[dict[str, Any]]
) -> None:
    present = {record["provider"] for record in records}
    missing = sorted(set(manifest["selected_providers"]) - present)
    if missing:
        raise RunIntegrityError(
            f"No prediction records at all for provider(s) selected in this run: {missing}"
        )


def write_metrics(run_dir: Path, metrics: dict[str, Any]) -> None:
    atomic_write_json(run_dir / "metrics.json", metrics)
