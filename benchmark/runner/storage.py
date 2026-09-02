"""Output-directory and artifact writing for the evaluation runner
(Issue #89): manifest.json (whole-file, atomically replaced) and
predictions.jsonl (append-only, one line per attempted (case, provider)
pair, flushed immediately after every write).
"""

from __future__ import annotations

import json
import secrets
from datetime import UTC, datetime
from pathlib import Path

from benchmark.atomic_write import atomic_write_json
from benchmark.runner.models import PredictionResult, RunManifest

DEFAULT_RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def new_run_id() -> str:
    """UTC timestamp (second precision) plus a short random suffix, so two
    runs started in the same second still can't collide; used as both
    the default output directory name and the run_id recorded in every
    artifact.
    """
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    suffix = secrets.token_hex(3)
    return f"{timestamp}-{suffix}"


def prepare_output_dir(output_dir: Path) -> Path:
    """Creates output_dir fresh. Refuses to reuse an existing directory -
    a previous run's artifacts must never be silently overwritten.
    Parents are created as needed, matching a plain path a developer
    might pass with --output.
    """
    if output_dir.exists():
        raise FileExistsError(
            f"Output directory already exists, refusing to overwrite: {output_dir}"
        )

    output_dir.mkdir(parents=True)
    return output_dir


def write_manifest(output_dir: Path, manifest: RunManifest) -> None:
    """Atomically replaces manifest.json (see atomic_write_json). Called
    once at the start of a run (status="running") and again at the end
    ("complete"/"interrupted"); see cli.py.
    """
    atomic_write_json(output_dir / "manifest.json", manifest.to_dict())


class PredictionWriter:
    """Appends one JSON line per PredictionResult to predictions.jsonl,
    flushing after every write so the file always reflects real progress
    - matters specifically for an interrupted run (see cli.py), where
    everything written before the interruption should remain readable.
    """

    def __init__(self, output_dir: Path):
        self._file = (output_dir / "predictions.jsonl").open("w")

    def write(self, result: PredictionResult) -> None:
        self._file.write(json.dumps(result.to_dict(), sort_keys=True))
        self._file.write("\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> PredictionWriter:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
