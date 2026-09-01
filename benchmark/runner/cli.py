"""Developer CLI for the evaluation runner (Issue #89):

    python -m benchmark.runner --providers gemini openbiollm medgemma

See benchmark/README.md for full usage. This module owns argument
parsing, credential loading, case/tag filtering, and the manifest
lifecycle (written "running" at the start, "complete"/"interrupted" at
the end); actual per-case/per-provider execution lives in execution.py,
and artifact writing lives in storage.py, so this file stays a thin
orchestrator.

This is a developer/research tool, not a MedLens application feature -
it is never imported by, or exposed through, the FastAPI app.
"""

from __future__ import annotations

import argparse
import platform
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from app.ai.prompts import build_summary_prompt
from benchmark.loader import BenchmarkCase, load_cases
from benchmark.runner.execution import run_case_for_provider, utc_now_iso
from benchmark.runner.models import RunManifest, benchmark_fingerprint, prompt_hash
from benchmark.runner.providers import (
    PROVIDER_NAMES,
    build_provider,
    generation_params_for,
    inference_backend_for,
    runtime_version_for,
)
from benchmark.runner.storage import (
    DEFAULT_RESULTS_DIR,
    PredictionWriter,
    new_run_id,
    prepare_output_dir,
    write_manifest,
)

# The same file/location app/core/config.py's Settings reads
# (SettingsConfigDict(env_file=".env")), reused here so a developer's
# existing GEMINI_API_KEY/OPENBIOLLM_MODEL/MEDGEMMA_MODEL/OLLAMA_BASE_URL
# "just work" without a second copy; see _load_env() below.
_BACKEND_ENV_PATH = Path(__file__).resolve().parent.parent.parent / "backend" / ".env"


def _load_env() -> None:
    """Best-effort load of backend/.env. override=False: a credential
    already exported into the process environment always wins over the
    file; this must keep working with no backend/.env present at all
    (e.g. CI, or a developer who exports credentials directly), so this
    never raises when the file is missing.

    Deliberately does not construct app.core.config.Settings: Settings()
    requires DATABASE_URL/JWT_SECRET_KEY (unrelated to AI evaluation, no
    defaults) and its own AI_PROVIDER validation assumes exactly one
    active provider, neither of which this multi-provider runner needs
    or wants. See benchmark/README.md for the full reasoning.
    """
    load_dotenv(_BACKEND_ENV_PATH, override=False)


def _git_metadata() -> tuple[str | None, bool | None]:
    """Best-effort git commit SHA and dirty-working-tree flag; both None
    if this isn't a git checkout or git isn't on PATH. Reproducibility
    metadata is a nice-to-have here, not a requirement to run at all, so
    this never raises.
    """
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout.strip()
        status_output = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        ).stdout
        return commit, bool(status_output.strip())
    except (OSError, subprocess.SubprocessError):
        return None, None


def _filter_cases(
    cases: list[BenchmarkCase], case_ids: list[str] | None, tags: list[str] | None
) -> list[BenchmarkCase]:
    """--cases and --tags are intersected when both are given: a case
    must match both filters to be selected. This is the intuitive
    reading of "run these specific cases, restricted to this tag";
    a union would silently pull in cases neither filter alone asked for.
    """
    selected = cases
    if case_ids is not None:
        wanted_ids = set(case_ids)
        selected = [case for case in selected if case.case_id in wanted_ids]
    if tags is not None:
        wanted_tags = set(tags)
        selected = [case for case in selected if wanted_tags & set(case.tags)]
    return selected


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m benchmark.runner",
        description=(
            "Runs the synthetic medication-extraction benchmark (benchmark/cases/) "
            "against one or more real AIProvider implementations and records structured "
            "predictions/results for later scoring (Issue #90/#91). Computes no quality "
            "metric of its own."
        ),
    )
    parser.add_argument(
        "--providers",
        nargs="+",
        choices=PROVIDER_NAMES,
        default=list(PROVIDER_NAMES),
        help="Which providers to evaluate (default: all supported providers).",
    )
    parser.add_argument(
        "--cases",
        nargs="+",
        default=None,
        metavar="CASE_ID",
        help="Restrict to these benchmark case ids (e.g. BENCH-001). Default: every case.",
    )
    parser.add_argument(
        "--tags",
        nargs="+",
        default=None,
        metavar="TAG",
        help=(
            "Restrict to cases carrying at least one of these tags. Combined with --cases "
            "as an intersection when both are given. Default: every tag."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            "Output directory for this run's artifacts (default: "
            "benchmark/results/<UTC timestamp>-<random suffix>/). Must not already exist."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    _load_env()

    cases = load_cases()
    selected_cases = _filter_cases(cases, args.cases, args.tags)
    if not selected_cases:
        print("No benchmark cases matched the given --cases/--tags filters.", file=sys.stderr)
        return 1

    run_id = new_run_id()
    output_dir = args.output or (DEFAULT_RESULTS_DIR / run_id)
    try:
        prepare_output_dir(output_dir)
    except FileExistsError as error:
        print(str(error), file=sys.stderr)
        return 1

    providers = {name: build_provider(name) for name in args.providers}
    git_commit, git_dirty = _git_metadata()

    manifest = RunManifest(
        run_id=run_id,
        started_at=utc_now_iso(),
        completed_at=None,
        status="running",
        benchmark_fingerprint=benchmark_fingerprint(cases),
        case_count=len(selected_cases),
        selected_providers=list(providers.keys()),
        case_filter=args.cases,
        tag_filter=args.tags,
        providers={
            name: {
                "model": provider.model,
                "inference_backend": inference_backend_for(provider),
                "generation_params": generation_params_for(provider),
                "runtime_version": runtime_version_for(provider),
            }
            for name, provider in providers.items()
        },
        git_commit=git_commit,
        git_dirty=git_dirty,
        python_version=platform.python_version(),
        predictions_file="predictions.jsonl",
        result_count=0,
    )
    write_manifest(output_dir, manifest)

    result_count = 0
    status = "complete"
    try:
        with PredictionWriter(output_dir) as writer:
            for case in selected_cases:
                prompt = build_summary_prompt(case.input_notes)
                hash_value = prompt_hash(prompt)
                for provider_name, provider in providers.items():
                    result = run_case_for_provider(
                        run_id=run_id,
                        case=case,
                        provider_name=provider_name,
                        provider=provider,
                        prompt=prompt,
                        prompt_hash_value=hash_value,
                    )
                    writer.write(result)
                    result_count += 1
    except KeyboardInterrupt:
        status = "interrupted"
    finally:
        manifest.status = status
        manifest.completed_at = utc_now_iso()
        manifest.result_count = result_count
        write_manifest(output_dir, manifest)

    print(f"Wrote {result_count} prediction(s) to {output_dir} (status: {status})")
    return 0 if status == "complete" else 130
