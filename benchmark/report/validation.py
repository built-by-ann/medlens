"""Cross-run comparability checks for a report (Issue #91).

A report can cite providers from different `benchmark.runner` (#89) runs,
for example Gemini from a clean Gemini-only run and OpenBioLLM/MedGemma
from a run where Gemini's own calls were separately affected by an
unrelated billing-account issue. Before rendering anything, every check here
confirms those runs are actually safe to place side by side: same
dataset state, same exact prompts, same case population. None of this
exists in `benchmark/metrics/` (Issue #90), which only ever validates
one run against itself; #90 stays completely unmodified.

Every check is fail-loud by default, matching `benchmark/metrics/io.py`'s
own philosophy: silently comparing providers scored under different
conditions would make the resulting report scientifically misleading.
"""

from __future__ import annotations

from dataclasses import dataclass

from benchmark.report.sources import ProviderSource, ReportIntegrityError


@dataclass(frozen=True)
class ValidationWarning:
    """A comparability concern real enough to surface prominently in the
    report's own provenance section, but not severe enough to refuse to
    build the report at all (unlike everything checked in validate_sources'
    other checks, which raise ReportIntegrityError instead).
    """

    message: str


def validate_sources(sources: list[ProviderSource]) -> list[ValidationWarning]:
    """Raises ReportIntegrityError for a hard comparability failure.
    Returns the list of non-fatal warnings to render, never silently
    absorbed either way.
    """
    _check_fingerprints_match(sources)
    _check_case_sets_match(sources)
    _check_prompt_hashes_match(sources)
    return _check_git_commits(sources)


def _check_fingerprints_match(sources: list[ProviderSource]) -> None:
    """The dataset state a run measured against; a mismatch means the
    cited runs were not scored against the same benchmark content at all,
    the single most fundamental comparability requirement.
    """
    fingerprints = {source.manifest["benchmark_fingerprint"] for source in sources}
    if len(fingerprints) > 1:
        detail = ", ".join(
            f"{source.provider} ({source.run_id}): {source.manifest['benchmark_fingerprint']}"
            for source in sources
        )
        raise ReportIntegrityError(
            "Cited runs were executed against different benchmark dataset states "
            f"(benchmark_fingerprint mismatch): {detail}"
        )


def _own_records(source: ProviderSource) -> list[dict]:
    """source.predictions is expected to already be filtered to this
    provider's own records (see sources.py's _read_predictions).
    Filtered again here, defensively: one run directory can hold several
    providers' records interleaved in a single predictions.jsonl, and
    validation must never silently draw a case_id/prompt_hash from a
    different provider's record just because it happened to share this
    source's run directory.
    """
    return [record for record in source.predictions if record["provider"] == source.provider]


def _check_case_sets_match(sources: list[ProviderSource]) -> None:
    """Every cited run must cover exactly the same benchmark cases: a
    partial run mixed with a full one would silently change the
    denominators being compared.
    """
    case_id_sets = {
        source.provider: frozenset(record["case_id"] for record in _own_records(source))
        for source in sources
    }
    reference_provider, reference_case_ids = next(iter(case_id_sets.items()))
    mismatched = {
        provider: case_ids
        for provider, case_ids in case_id_sets.items()
        if case_ids != reference_case_ids
    }
    if mismatched:
        detail = ", ".join(
            f"{provider} has {len(case_ids)} case(s)" for provider, case_ids in mismatched.items()
        )
        raise ReportIntegrityError(
            "Cited runs do not cover the same set of benchmark cases: "
            f"{reference_provider} has {len(reference_case_ids)} case(s); {detail}"
        )


def _check_prompt_hashes_match(sources: list[ProviderSource]) -> None:
    """For any case_id shared by more than one cited run, the exact
    prompt sent must be identical (identified by its recorded
    prompt_hash). This is the finer-grained companion to the fingerprint
    check above, confirming not just "the dataset matched" but "the
    literal same prompt string was sent" for every shared case.
    """
    first_seen: dict[str, tuple[str, str]] = {}  # case_id -> (prompt_hash, provider)
    mismatches: list[tuple[str, str, str, str, str]] = []

    for source in sources:
        for record in _own_records(source):
            case_id = record["case_id"]
            prompt_hash = record["prompt_hash"]
            if case_id not in first_seen:
                first_seen[case_id] = (prompt_hash, source.provider)
                continue
            existing_hash, existing_provider = first_seen[case_id]
            if existing_hash != prompt_hash:
                mismatches.append(
                    (case_id, existing_provider, existing_hash, source.provider, prompt_hash)
                )

    if mismatches:
        detail = "; ".join(
            f"{case_id}: {provider_a}={hash_a} vs {provider_b}={hash_b}"
            for case_id, provider_a, hash_a, provider_b, hash_b in mismatches
        )
        raise ReportIntegrityError(f"Prompt hash mismatch across cited runs for: {detail}")


def _check_git_commits(sources: list[ProviderSource]) -> list[ValidationWarning]:
    """A code-state difference between cited runs isn't automatically
    disqualifying (an unrelated documentation-only commit between two
    runs doesn't change what was measured), so this warns rather than
    raises. It must still never be silently absorbed, though, since it
    *could* matter (a prompt or scoring change between runs would).
    """
    commits = {source.manifest.get("git_commit") for source in sources}
    if len(commits) > 1:
        detail = ", ".join(
            f"{source.provider}={source.manifest.get('git_commit')}" for source in sources
        )
        return [ValidationWarning(f"Cited runs were produced from different git commits: {detail}")]
    return []
