"""Structured result types for the evaluation runner (Issue #89).

Two shapes: PredictionResult (one per attempted (case, provider) pair,
written as one line of predictions.jsonl; see storage.py) and
RunManifest (one per run, written as manifest.json). Both are plain
dataclasses with an explicit to_dict() rather than Pydantic models;
nothing here is ever parsed back into a validated shape the way
ClinicalSummary is; these are pure output structures, not something an
input is ever checked against, so a dataclass is enough.

Also defines benchmark_fingerprint() (what dataset state a run was
executed against) and prompt_hash() (the identical-prompt reproducibility
guarantee; see execution.py for where both are actually used).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from benchmark.loader import BenchmarkCase


def benchmark_fingerprint(cases: list[BenchmarkCase]) -> str:
    """A sha256 fingerprint of every loaded case's actual content.

    Stable across incidental file formatting: each case's raw dict is
    canonically re-serialized (sort_keys, no extra whitespace) before
    hashing, so a case file that's reformatted (reindented, keys
    reordered) without changing what it means hashes identically.
    Sensitive to any real content change, since that changes the
    canonical serialization itself. Cases are sorted by case_id first so
    the order load_cases() happened to return them in never affects the
    result.
    """
    canonical_parts = [
        json.dumps(case.raw, sort_keys=True, separators=(",", ":"))
        for case in sorted(cases, key=lambda case: case.case_id)
    ]
    digest = hashlib.sha256("\n".join(canonical_parts).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def prompt_hash(prompt: str) -> str:
    """A sha256 hash of the exact prompt string sent to every provider for
    one benchmark case; see execution.py's run_evaluation loop, which
    calls build_summary_prompt() exactly once per case and reuses both
    the string and this hash across every selected provider.
    """
    return f"sha256:{hashlib.sha256(prompt.encode('utf-8')).hexdigest()}"


@dataclass
class ParsingResult:
    json_valid: bool
    schema_valid: bool
    error_category: str | None
    error_message: str | None


@dataclass
class PredictionResult:
    """One attempted (benchmark case, provider) pair, one line of
    predictions.jsonl. provider_response is the exact string
    AIProvider.generate_summary() returned, before any evaluation-
    framework parsing or validation; see docs/ai.md and benchmark/
    README.md for why this is *not* the same thing as "the literal
    unprocessed SDK/model output" for OpenBioLLM/MedGemma (both perform
    intentional syntactic cleanup inside generate_summary() itself,
    invisible outside the provider), even though it genuinely is exactly
    that for Gemini.
    """

    run_id: str
    case_id: str
    case_tags: list[str]
    provider: str
    model: str
    inference_backend: str | None
    prompt_hash: str
    provider_response: str | None
    provider_call_succeeded: bool
    parsing: ParsingResult
    parsed_clinical_summary: dict[str, Any] | None
    latency_ms: float
    timestamp: str
    generation_params: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RunManifest:
    """Run-level metadata, written once at the start of a run
    (status="running") and once more at the end (status="complete" or
    "interrupted"); see storage.py's write_manifest() and cli.py's
    lifecycle around it. A manifest left at status="running" on disk with
    no update means the process crashed before finishing; this is
    deliberately not distinguished from a truly hung run; see
    benchmark/README.md's Reproducibility section.
    """

    run_id: str
    started_at: str
    completed_at: str | None
    status: str
    benchmark_fingerprint: str
    case_count: int
    selected_providers: list[str]
    case_filter: list[str] | None
    tag_filter: list[str] | None
    providers: dict[str, dict[str, Any]]
    git_commit: str | None
    git_dirty: bool | None
    python_version: str
    predictions_file: str
    result_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
