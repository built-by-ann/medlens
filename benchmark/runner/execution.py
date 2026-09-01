"""Per-case, per-provider execution and failure classification for the
evaluation runner (Issue #89).

The identical-prompt guarantee lives in cli.py's run loop, not here:
build_summary_prompt() is called exactly once per benchmark case, and the
resulting string (and its hash) is passed unchanged into
run_case_for_provider() below for every selected provider; this module
never rebuilds a prompt itself.

Parsing is deliberately done in two explicit stages, json.loads(), then
ClinicalSummary.model_validate(), rather than the one-line
ClinicalSummary.model_validate_json() AISummaryService._parse_response
uses in production (app/ai/service.py). Splitting it is what lets
invalid_json and schema_validation_error be told apart, which the
application itself has no need to do (see docs/ai.md's Structured Output
section: it deliberately collapses both into one AIProviderError).
Neither stage repairs, cleans, or otherwise modifies provider_response;
ClinicalSummary itself is used completely unmodified either way.
"""

from __future__ import annotations

import json
import time
import urllib.error
from datetime import UTC, datetime

from google.genai import errors as genai_errors
from pydantic import ValidationError as PydanticValidationError

from app.ai.providers.base import AIProvider, AIProviderError
from app.ai.schemas import ClinicalSummary
from benchmark.loader import BenchmarkCase
from benchmark.runner.models import ParsingResult, PredictionResult
from benchmark.runner.providers import generation_params_for, inference_backend_for

# Failure taxonomy, derived from the exception boundaries every
# AIProvider implementation already has (see docs/ai.md's Provider
# Abstraction / Error Handling sections and each provider module's own
# generate_summary()), not invented for this framework. Every provider
# raises exactly one AIProviderError for every failure; the *original*
# exception, when there is one, survives via Python's own exception
# chaining ("raise AIProviderError(...) from error" in every provider),
# which is what lets this module recover finer detail than the single
# exception type alone would give it, matched by isinstance against the
# real exception classes each provider itself catches, never by
# string-matching a class name (which would risk colliding with, e.g.,
# pydantic's own unrelated ValidationError).
_MISSING_CREDENTIAL_SUFFIX = "is not configured"
_EMPTY_RESPONSE_SUFFIX = "empty or invalid response"
_PROVIDER_ERROR_CAUSES = (genai_errors.APIError,)


def utc_now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _classify_provider_error(error: AIProviderError) -> str:
    """Maps a caught AIProviderError to one of the categories above.

    Known, deliberately-not-fixed asymmetry: GeminiProvider has no SDK
    exception distinct from a generic Exception for a network timeout;
    only genai_errors.APIError is caught specifically in
    gemini_provider.py, so a Gemini timeout classifies as
    unexpected_error, not timeout, unlike OpenBioLLM/MedGemma, which raise
    a bare TimeoutError (or a urllib.error.URLError wrapping one) that
    this function recognizes explicitly. This reflects a real,
    pre-existing difference between the provider implementations,
    documented here and in benchmark/README.md rather than papered over
    or "fixed" by modifying GeminiProvider as part of this issue.

    urllib.error.HTTPError is checked before urllib.error.URLError
    because it's a subclass of it; checking URLError first would shadow
    every HTTPError case (including model_not_found's 404).
    """
    if error.__cause__ is None:
        message = str(error)
        if message.endswith(_MISSING_CREDENTIAL_SUFFIX):
            return "missing_credential"
        if message.endswith(_EMPTY_RESPONSE_SUFFIX):
            return "empty_response"
        return "unexpected_error"

    cause = error.__cause__

    if isinstance(cause, TimeoutError):
        return "timeout"
    if isinstance(cause, urllib.error.HTTPError):
        return "model_not_found" if cause.code == 404 else "provider_error"
    if isinstance(cause, urllib.error.URLError):
        return "timeout" if isinstance(cause.reason, TimeoutError) else "connection_error"
    if isinstance(cause, _PROVIDER_ERROR_CAUSES):
        return "provider_error"
    return "unexpected_error"


def _parse(provider_response: str) -> tuple[ParsingResult, dict | None]:
    try:
        parsed_json = json.loads(provider_response)
    except json.JSONDecodeError as error:
        return (
            ParsingResult(
                json_valid=False,
                schema_valid=False,
                error_category="invalid_json",
                error_message=str(error),
            ),
            None,
        )

    try:
        clinical_summary = ClinicalSummary.model_validate(parsed_json)
    except PydanticValidationError as error:
        return (
            ParsingResult(
                json_valid=True,
                schema_valid=False,
                error_category="schema_validation_error",
                error_message=str(error),
            ),
            None,
        )

    return (
        ParsingResult(json_valid=True, schema_valid=True, error_category=None, error_message=None),
        clinical_summary.model_dump(),
    )


def run_case_for_provider(
    run_id: str,
    case: BenchmarkCase,
    provider_name: str,
    provider: AIProvider,
    prompt: str,
    prompt_hash_value: str,
) -> PredictionResult:
    """Runs exactly one (case, provider) pair, isolated: any Exception
    raised anywhere in this function, by the provider, or by JSON/schema
    parsing, is caught here and turned into a PredictionResult carrying
    the failure, never re-raised, so a single bad pair can never abort
    the run (see cli.py's run loop). A KeyboardInterrupt (or any other
    BaseException) deliberately is NOT caught here; it propagates up to
    cli.py's own run-level handler, which is what marks the whole run
    "interrupted" rather than silently swallowing the interrupt as if it
    were just another provider failure.
    """
    started_at = time.monotonic()
    timestamp = utc_now_iso()
    inference_backend = inference_backend_for(provider)
    generation_params = generation_params_for(provider)

    def _elapsed_ms() -> float:
        return round((time.monotonic() - started_at) * 1000, 1)

    def _failure(category: str, message: str) -> PredictionResult:
        return PredictionResult(
            run_id=run_id,
            case_id=case.case_id,
            case_tags=list(case.tags),
            provider=provider_name,
            model=provider.model,
            inference_backend=inference_backend,
            prompt_hash=prompt_hash_value,
            provider_response=None,
            provider_call_succeeded=False,
            parsing=ParsingResult(
                json_valid=False,
                schema_valid=False,
                error_category=category,
                error_message=message,
            ),
            parsed_clinical_summary=None,
            latency_ms=_elapsed_ms(),
            timestamp=timestamp,
            generation_params=generation_params,
        )

    try:
        provider_response = provider.generate_summary(prompt)
    except AIProviderError as error:
        # error's own message is already safe to expose (every provider
        # writes it that way; see docs/ai.md's Error Handling section);
        # the underlying cause's message never is, so only its type is
        # ever inspected (_classify_provider_error), never its str().
        return _failure(_classify_provider_error(error), str(error))
    except Exception as error:
        # Defensive net only; every provider is designed to always wrap
        # its own failures into AIProviderError, so reaching here means a
        # provider implementation bug, not an expected outcome. The raw
        # exception text has never been vetted as safe to expose (unlike
        # AIProviderError's own message), so only the exception's type
        # name is recorded, never str(error); see docs/ai.md's
        # sanitized-error-message convention.
        return _failure(
            "unexpected_error", f"Unexpected error escaped provider: {type(error).__name__}"
        )

    parsing, parsed = _parse(provider_response)
    return PredictionResult(
        run_id=run_id,
        case_id=case.case_id,
        case_tags=list(case.tags),
        provider=provider_name,
        model=provider.model,
        inference_backend=inference_backend,
        prompt_hash=prompt_hash_value,
        provider_response=provider_response,
        provider_call_succeeded=True,
        parsing=parsing,
        parsed_clinical_summary=parsed,
        latency_ms=_elapsed_ms(),
        timestamp=timestamp,
        generation_params=generation_params,
    )
