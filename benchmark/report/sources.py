"""Loads and resolves the artifacts a comparison report is built from
(Issue #91).

Each `--provider NAME=RUN_ID` citation names one existing
`benchmark/results/<run_id>/` directory, already produced by
`benchmark.runner` (#89) and already scored by `benchmark.metrics` (#90).
This module never computes scoring itself and never calls an AIProvider;
it only reads `manifest.json`/`metrics.json`/`predictions.jsonl` exactly
as #89/#90 wrote them, the same "pure reader of already-produced
artifacts" boundary `benchmark/metrics/io.py` keeps for a single run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ReportIntegrityError(Exception):
    """Raised for any condition under which building a report would be
    scientifically misleading: a missing artifact, an unknown provider,
    or (see validation.py) a cross-run comparability problem. Mirrors
    benchmark.metrics.io.RunIntegrityError's fail-loud philosophy,
    applied to a different, cross-run class of problem #90 never had to
    consider (it only ever validates one run against itself).
    """


# benchmark/results/ (Issue #89's own gitignored output location), the
# default place a bare run_id (not an existing path) is resolved
# against.
DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def parse_provider_mapping(raw_args: list[str]) -> dict[str, str]:
    """Parses repeated `--provider NAME=RUN_ID` values into
    {name: run_id}, preserving citation order (dict insertion order),
    since the report renders providers in the order they were cited on
    the command line. This is deliberately not alphabetized, so the CLI
    invocation itself controls presentation order.
    """
    mapping: dict[str, str] = {}
    for raw in raw_args:
        name, sep, run_id = raw.partition("=")
        name = name.strip()
        run_id = run_id.strip()
        if not sep or not name or not run_id:
            raise ReportIntegrityError(f"Invalid --provider value {raw!r}: expected NAME=RUN_ID")
        if name in mapping:
            raise ReportIntegrityError(f"Provider {name!r} was cited more than once")
        mapping[name] = run_id

    if not mapping:
        raise ReportIntegrityError("At least one --provider NAME=RUN_ID is required")

    return mapping


def _read_json(path: Path, what: str) -> dict[str, Any]:
    if not path.exists():
        raise ReportIntegrityError(f"No {what} found at {path}")
    return json.loads(path.read_text())


def _read_predictions(path: Path, provider: str) -> list[dict[str, Any]]:
    """One run's predictions.jsonl holds every selected provider's
    records interleaved in one file (see benchmark/runner/storage.py).
    A run citing "openbiollm" and "medgemma" from the same run_dir is
    exactly the normal case, not an edge case, so filtering to this
    provider's own records here is required, not optional. Every
    downstream consumer of ProviderSource.predictions (validation.py,
    qualitative.py) depends on this already being scoped correctly;
    provider identity must never be inferred solely from which run_dir a
    record came from.
    """
    if not path.exists():
        raise ReportIntegrityError(f"No predictions.jsonl found at {path}")
    records = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if record.get("provider") == provider:
            records.append(record)
    return records


@dataclass(frozen=True)
class ProviderSource:
    """Everything resolved for one cited `NAME=RUN_ID` pair: the run's
    manifest/metrics documents in full (other providers' entries stay
    accessible for provenance cross-checks), this provider's own two
    sub-entries, and this provider's own records from this run's raw
    predictions.jsonl, already filtered to `record["provider"] ==
    provider` and never the whole file's contents, since one run directory
    can (and typically does) hold more than one provider's records.
    Predictions are read-only and only used for qualitative.py's
    possible_inconsistencies/summary excerpts, since metrics.json never
    carries those two fields at all.
    """

    provider: str
    run_id: str
    run_dir: Path
    manifest: dict[str, Any]
    metrics_doc: dict[str, Any]
    provider_manifest: dict[str, Any]
    provider_metrics: dict[str, Any]
    predictions: list[dict[str, Any]]


def load_provider_source(
    provider: str, run_id: str, results_dir: Path = DEFAULT_RESULTS_DIR
) -> ProviderSource:
    """Resolves one --provider citation into its full ProviderSource.
    run_id is treated as an existing path first (so a caller can point at
    a run directory anywhere), falling back to results_dir/run_id (the
    common case: a bare run_id like "20260901-170758-31889a").
    """
    run_dir = Path(run_id)
    if not run_dir.exists():
        run_dir = results_dir / run_id
    if not run_dir.is_dir():
        raise ReportIntegrityError(
            f"No run directory found for {run_id!r} (looked for {run_dir})"
        )

    manifest = _read_json(run_dir / "manifest.json", "manifest.json")
    selected = manifest.get("selected_providers", [])
    if provider not in selected:
        raise ReportIntegrityError(
            f"Provider {provider!r} was not selected in run {run_id!r} "
            f"(selected_providers: {selected})"
        )

    metrics_path = run_dir / "metrics.json"
    if not metrics_path.exists():
        raise ReportIntegrityError(
            f"No metrics.json in {run_dir}. Run `python -m benchmark.metrics {run_dir}` "
            "first (this tool only reads an already-scored run; it never scores one itself)."
        )
    metrics_doc = json.loads(metrics_path.read_text())

    provider_manifest = manifest.get("providers", {}).get(provider)
    if provider_manifest is None:
        raise ReportIntegrityError(f"Run {run_id!r} manifest has no providers[{provider!r}] entry")

    provider_metrics = metrics_doc.get("providers", {}).get(provider)
    if provider_metrics is None:
        raise ReportIntegrityError(
            f"metrics.json in {run_dir} has no providers[{provider!r}] entry. Was it "
            "generated before this provider was added to the run?"
        )

    predictions = _read_predictions(run_dir / "predictions.jsonl", provider)

    return ProviderSource(
        provider=provider,
        run_id=run_id,
        run_dir=run_dir,
        manifest=manifest,
        metrics_doc=metrics_doc,
        provider_manifest=provider_manifest,
        provider_metrics=provider_metrics,
        predictions=predictions,
    )


def load_all_sources(
    provider_to_run_id: dict[str, str], results_dir: Path = DEFAULT_RESULTS_DIR
) -> dict[str, ProviderSource]:
    """Preserves provider_to_run_id's own order (report rendering order)."""
    return {
        provider: load_provider_source(provider, run_id, results_dir)
        for provider, run_id in provider_to_run_id.items()
    }
