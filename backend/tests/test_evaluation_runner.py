"""Tests for the evaluation runner (benchmark/runner/, Issue #89).

No test here makes a real network call; every provider exercised for
orchestration/parsing/failure-isolation behavior is a hand-written fake
(this codebase avoids a mocking library, see docs/testing.md), the same
convention every other AI test in this suite already follows. The tests
that do construct real provider classes (GeminiProvider/OpenBioLLMProvider/
MedGemmaProvider) only inspect their attributes/module constants; they
never call generate_summary(), so no client is ever built and no request
is ever made.

benchmark/ is a top-level directory, a sibling of backend/ (see
benchmark/README.md), not part of the `app` package under test everywhere
else in this suite. sys.path is extended here the same way
test_benchmark_dataset.py already does, since this is the other test file
that needs it.
"""

import json
import sys
import urllib.error
from pathlib import Path

import pytest
from google.genai import errors as genai_errors

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from benchmark.loader import BenchmarkCase, load_cases  # noqa: E402
from benchmark.runner import cli, storage  # noqa: E402
from benchmark.runner.execution import run_case_for_provider  # noqa: E402
from benchmark.runner.models import benchmark_fingerprint, prompt_hash  # noqa: E402
from benchmark.runner.providers import PROVIDER_NAMES, build_provider  # noqa: E402

from app.ai.prompts import build_summary_prompt  # noqa: E402
from app.ai.providers.base import AIProvider, AIProviderError  # noqa: E402

# --- fixtures / fakes ----------------------------------------------------


def _case(case_id="BENCH-TEST-1", tags=None, input_notes=None) -> BenchmarkCase:
    input_notes = input_notes or ["Patient takes Lisinopril 10 mg oral once daily."]
    tags = tags or ["straightforward_list"]
    raw = {
        "case_id": case_id,
        "tags": tags,
        "difficulty": "easy",
        "description": "test case",
        "input_notes": input_notes,
        "expected": {"medications": [], "possible_inconsistencies": [], "summary": "x"},
    }
    return BenchmarkCase(
        case_id=case_id,
        tags=tags,
        difficulty="easy",
        description="test case",
        input_notes=input_notes,
        expected=raw["expected"],
        source_path=Path(f"/fake/{case_id}.json"),
        raw=raw,
    )


VALID_RESPONSE = json.dumps(
    {
        "medications": [{"name": "Lisinopril", "dosage": "10 mg"}],
        "possible_inconsistencies": [],
        "summary": "ok",
    }
)


class FakeProvider(AIProvider):
    """A hand-written fake AIProvider, no mocking library, matching this
    repo's established convention (see e.g. test_ai_service.py's own
    FakeProvider). Records every prompt it was called with, for the
    identical-prompt tests.
    """

    def __init__(self, name="fake", model="fake-model", response=VALID_RESPONSE, error=None):
        self.name = name
        self.model = model
        self._response = response
        self._error = error
        self.received_prompts: list[str] = []

    def generate_summary(self, prompt: str) -> str:
        self.received_prompts.append(prompt)
        if self._error is not None:
            raise self._error
        return self._response


def _run_one(case, provider, provider_name="fake"):
    prompt = build_summary_prompt(case.input_notes)
    return run_case_for_provider(
        run_id="test-run",
        case=case,
        provider_name=provider_name,
        provider=provider,
        prompt=prompt,
        prompt_hash_value=prompt_hash(prompt),
    )


# --- benchmark loading reuse ----------------------------------------------


def test_cli_reuses_the_real_benchmark_loader():
    # No reimplementation of loading/validation; cli.py imports the exact
    # same load_cases function benchmark/README.md documents as the one
    # entry point (see benchmark/loader.py's own module docstring).
    assert cli.load_cases is load_cases


# --- one case / one provider -----------------------------------------------


def test_run_case_for_provider_success():
    case = _case()
    provider = FakeProvider()

    result = _run_one(case, provider)

    assert result.provider_call_succeeded is True
    assert result.parsing.json_valid is True
    assert result.parsing.schema_valid is True
    assert result.parsing.error_category is None
    assert result.parsed_clinical_summary["medications"][0]["name"] == "Lisinopril"
    assert result.provider_response == VALID_RESPONSE
    assert result.case_id == case.case_id
    assert result.case_tags == case.tags


# --- one case / multiple providers, identical prompt ------------------------


def test_identical_prompt_sent_to_every_provider():
    case = _case()
    fakes = {
        "gemini": FakeProvider(name="gemini"),
        "openbiollm": FakeProvider(name="openbiollm"),
        "medgemma": FakeProvider(name="medgemma"),
    }
    prompt = build_summary_prompt(case.input_notes)
    hash_value = prompt_hash(prompt)

    results = [
        run_case_for_provider(
            run_id="r",
            case=case,
            provider_name=name,
            provider=p,
            prompt=prompt,
            prompt_hash_value=hash_value,
        )
        for name, p in fakes.items()
    ]

    for fake in fakes.values():
        assert fake.received_prompts == [prompt]
    assert {r.prompt_hash for r in results} == {hash_value}


def test_prompt_hash_is_stable_and_content_sensitive():
    prompt_a = build_summary_prompt(["Note text A."])
    prompt_a_again = build_summary_prompt(["Note text A."])
    prompt_b = build_summary_prompt(["Note text B."])

    assert prompt_hash(prompt_a) == prompt_hash(prompt_a_again)
    assert prompt_hash(prompt_a) != prompt_hash(prompt_b)
    assert prompt_hash(prompt_a).startswith("sha256:")


# --- provider_response preservation / parsing stages ------------------------


def test_provider_response_preserved_when_json_is_invalid():
    case = _case()
    provider = FakeProvider(response="not json at all")

    result = _run_one(case, provider)

    assert result.provider_call_succeeded is True
    assert result.provider_response == "not json at all"
    assert result.parsing.json_valid is False
    assert result.parsing.schema_valid is False
    assert result.parsing.error_category == "invalid_json"
    assert result.parsed_clinical_summary is None


def test_schema_validation_error_when_json_valid_but_shape_is_wrong():
    case = _case()
    provider = FakeProvider(response=json.dumps({"medications": "not-a-list"}))

    result = _run_one(case, provider)

    assert result.provider_call_succeeded is True
    assert result.provider_response is not None
    assert result.parsing.json_valid is True
    assert result.parsing.schema_valid is False
    assert result.parsing.error_category == "schema_validation_error"
    assert result.parsed_clinical_summary is None


def test_successful_parsing_yields_a_plain_dict_matching_clinical_summary():
    case = _case()
    provider = FakeProvider()

    result = _run_one(case, provider)

    assert result.parsed_clinical_summary == {
        "medications": [
            {
                "name": "Lisinopril",
                "dosage": "10 mg",
                "route": None,
                "frequency": None,
                "status": None,
                "notes": None,
                "source_note": None,
            }
        ],
        "possible_inconsistencies": [],
        "summary": "ok",
    }


# --- failure isolation and classification -----------------------------------


def test_provider_failure_classified_missing_credential():
    case = _case()
    provider = FakeProvider(error=AIProviderError("Fake API key is not configured"))

    result = _run_one(case, provider)

    assert result.provider_call_succeeded is False
    assert result.provider_response is None
    assert result.parsing.error_category == "missing_credential"


def test_provider_failure_classified_empty_response():
    case = _case()
    provider = FakeProvider(error=AIProviderError("Fake returned an empty or invalid response"))

    result = _run_one(case, provider)

    assert result.parsing.error_category == "empty_response"


def test_provider_failure_classified_timeout():
    error = AIProviderError("Fake request timed out after 120.0s")
    error.__cause__ = TimeoutError("timed out")
    provider = FakeProvider(error=error)

    result = _run_one(_case(), provider)

    assert result.parsing.error_category == "timeout"


def test_provider_failure_classified_timeout_when_urlerror_wraps_one():
    # The connection-phase equivalent of a bare TimeoutError (see
    # openbiollm_provider.py/medgemma_provider.py's own handling) - both
    # must classify as "timeout", not "connection_error".
    error = AIProviderError("Fake request timed out after 120.0s")
    error.__cause__ = urllib.error.URLError(TimeoutError("timed out"))
    provider = FakeProvider(error=error)

    result = _run_one(_case(), provider)

    assert result.parsing.error_category == "timeout"


def test_provider_failure_classified_connection_error():
    error = AIProviderError("Could not connect to Ollama at http://localhost:11434")
    error.__cause__ = urllib.error.URLError(ConnectionRefusedError("refused"))
    provider = FakeProvider(error=error)

    result = _run_one(_case(), provider)

    assert result.parsing.error_category == "connection_error"


def test_provider_failure_classified_model_not_found():
    http_error = urllib.error.HTTPError(
        url="http://localhost:11434/api/chat", code=404, msg="Not Found", hdrs=None, fp=None
    )
    error = AIProviderError("Ollama model 'x' is not installed. Run: ollama pull x")
    error.__cause__ = http_error
    provider = FakeProvider(error=error)

    result = _run_one(_case(), provider)

    assert result.parsing.error_category == "model_not_found"


def test_provider_failure_classified_provider_error():
    error = AIProviderError("Fake request failed: ClientError")
    error.__cause__ = genai_errors.ClientError(503, {"message": "unavailable"}, None)
    provider = FakeProvider(error=error)

    result = _run_one(_case(), provider)

    assert result.parsing.error_category == "provider_error"


def test_unexpected_exception_from_provider_is_isolated_and_sanitized():
    provider = FakeProvider(error=RuntimeError("a secret-looking detail: sk-abc123"))

    result = _run_one(_case(), provider)

    assert result.provider_call_succeeded is False
    assert result.parsing.error_category == "unexpected_error"
    # Only the exception's type is ever recorded for this defensive
    # branch, never its message; see execution.py's own comment.
    assert "sk-abc123" not in (result.parsing.error_message or "")
    assert "RuntimeError" in result.parsing.error_message


def test_latency_and_timestamp_metadata_are_populated():
    result = _run_one(_case(), FakeProvider())

    assert isinstance(result.latency_ms, float)
    assert result.latency_ms >= 0
    assert result.timestamp.endswith("Z")


# --- provider/generation metadata (real provider classes, no network) ------


def test_inference_backend_and_generation_params_for_real_providers():
    from benchmark.runner.providers import generation_params_for, inference_backend_for

    from app.ai.providers.gemini_provider import GeminiProvider
    from app.ai.providers.medgemma_provider import MedGemmaProvider
    from app.ai.providers.openbiollm_provider import OpenBioLLMProvider

    gemini = GeminiProvider(api_key="unused")
    assert inference_backend_for(gemini) is None
    assert generation_params_for(gemini) == {}

    openbiollm = OpenBioLLMProvider()
    assert inference_backend_for(openbiollm) == "ollama"
    assert generation_params_for(openbiollm)["seed"] == 0

    medgemma = MedGemmaProvider()
    assert inference_backend_for(medgemma) == "ollama"
    assert generation_params_for(medgemma)["temperature"] == 0


def test_runtime_version_for_returns_none_for_gemini():
    from benchmark.runner.providers import runtime_version_for

    from app.ai.providers.gemini_provider import GeminiProvider

    assert runtime_version_for(GeminiProvider(api_key="unused")) is None


def test_runtime_version_for_degrades_to_none_when_ollama_is_unreachable(monkeypatch):
    # No real Ollama server runs in CI (see docs/testing.md); an
    # unreachable server must degrade to None here, not raise - a run's
    # actual cases still surface a loud, per-case connection_error if
    # Ollama genuinely isn't reachable (see execution.py). Mocked, like
    # every other provider test in this suite, rather than making a real
    # connection attempt to an unused port.
    from benchmark.runner import providers as providers_module
    from benchmark.runner.providers import runtime_version_for

    from app.ai.providers.openbiollm_provider import OpenBioLLMProvider

    def _fake_urlopen(url, timeout=None):
        raise urllib.error.URLError(ConnectionRefusedError("refused"))

    monkeypatch.setattr(providers_module.urllib.request, "urlopen", _fake_urlopen)

    provider = OpenBioLLMProvider(base_url="http://localhost:11434")

    assert runtime_version_for(provider) is None


def test_runtime_version_for_reads_the_ollama_version_endpoint(monkeypatch):
    from benchmark.runner import providers as providers_module
    from benchmark.runner.providers import runtime_version_for

    from app.ai.providers.openbiollm_provider import OpenBioLLMProvider

    requested_urls = []

    class _FakeResponse:
        def read(self):
            return json.dumps({"version": "0.33.2"}).encode("utf-8")

        def __enter__(self):
            return self

        def __exit__(self, *exc_info):
            return False

    def _fake_urlopen(url, timeout=None):
        requested_urls.append(url)
        return _FakeResponse()

    monkeypatch.setattr(providers_module.urllib.request, "urlopen", _fake_urlopen)

    provider = OpenBioLLMProvider(base_url="http://localhost:11434")
    version = runtime_version_for(provider)

    assert version == "0.33.2"
    assert requested_urls == ["http://localhost:11434/api/version"]


def test_build_provider_reads_credential_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    provider = build_provider("gemini")

    assert provider._api_key == "test-gemini-key"


def test_build_provider_uses_the_providers_own_default_model():
    provider = build_provider("openbiollm")

    assert provider.model == "openbiollm-llama3-instruct"


def test_build_provider_reads_openbiollm_config_from_env(monkeypatch):
    monkeypatch.setenv("OPENBIOLLM_MODEL", "custom-openbiollm-tag")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://example-host:11434")

    provider = build_provider("openbiollm")

    assert provider.model == "custom-openbiollm-tag"
    assert provider.base_url == "http://example-host:11434"


def test_build_provider_reads_medgemma_config_from_env(monkeypatch):
    monkeypatch.setenv("MEDGEMMA_MODEL", "custom-medgemma-tag")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://example-host:11434")

    provider = build_provider("medgemma")

    assert provider.model == "custom-medgemma-tag"
    assert provider.base_url == "http://example-host:11434"


def test_build_provider_rejects_unknown_name():
    with pytest.raises(ValueError, match="Unknown provider"):
        build_provider("chatgpt")


def test_provider_registry_matches_documented_names():
    assert set(PROVIDER_NAMES) == {"gemini", "openbiollm", "medgemma"}


# --- CLI orchestration: multi-case/multi-provider failure isolation --------


def test_cli_continues_after_provider_and_case_failures(tmp_path, monkeypatch):
    cases = [
        _case("BENCH-A", input_notes=["Note A: Lisinopril 10 mg oral daily."]),
        _case("BENCH-B", input_notes=["Note B: Metformin 500 mg oral twice daily."]),
    ]
    monkeypatch.setattr(cli, "load_cases", lambda: cases)

    fakes = {
        "gemini": FakeProvider(name="gemini"),
        "openbiollm": FakeProvider(name="openbiollm", error=AIProviderError("boom")),
        "medgemma": FakeProvider(name="medgemma"),
    }
    monkeypatch.setattr(cli, "build_provider", lambda name: fakes[name])
    monkeypatch.setattr(cli, "_git_metadata", lambda: (None, None))
    monkeypatch.setattr(cli, "_load_env", lambda: None)

    output_dir = tmp_path / "run"
    exit_code = cli.main(
        ["--providers", "gemini", "openbiollm", "medgemma", "--output", str(output_dir)]
    )

    assert exit_code == 0
    lines = (output_dir / "predictions.jsonl").read_text().strip().splitlines()
    assert len(lines) == 6  # 2 cases x 3 providers: every pair attempted despite the failure

    records = {(r["case_id"], r["provider"]): r for r in (json.loads(line) for line in lines)}
    assert records[("BENCH-A", "gemini")]["provider_call_succeeded"] is True
    assert records[("BENCH-A", "openbiollm")]["provider_call_succeeded"] is False
    assert records[("BENCH-A", "medgemma")]["provider_call_succeeded"] is True
    # BENCH-B still ran in full despite BENCH-A's openbiollm failure.
    assert records[("BENCH-B", "gemini")]["provider_call_succeeded"] is True
    assert records[("BENCH-B", "openbiollm")]["provider_call_succeeded"] is False
    assert records[("BENCH-B", "medgemma")]["provider_call_succeeded"] is True


# --- manifest lifecycle ------------------------------------------------------


def test_manifest_written_running_then_complete(tmp_path, monkeypatch):
    cases = [_case("BENCH-A")]
    monkeypatch.setattr(cli, "load_cases", lambda: cases)
    monkeypatch.setattr(cli, "build_provider", lambda name: FakeProvider(name=name))
    monkeypatch.setattr(cli, "_git_metadata", lambda: ("abc1234", False))
    monkeypatch.setattr(cli, "_load_env", lambda: None)

    seen_statuses = []
    original_write = cli.write_manifest

    def _spy_write(out_dir, manifest):
        seen_statuses.append(manifest.status)
        original_write(out_dir, manifest)

    monkeypatch.setattr(cli, "write_manifest", _spy_write)

    output_dir = tmp_path / "run"
    exit_code = cli.main(["--providers", "gemini", "--output", str(output_dir)])

    assert exit_code == 0
    assert seen_statuses == ["running", "complete"]

    manifest = json.loads((output_dir / "manifest.json").read_text())
    assert manifest["status"] == "complete"
    assert manifest["completed_at"] is not None
    assert manifest["result_count"] == 1
    assert manifest["git_commit"] == "abc1234"
    assert manifest["git_dirty"] is False


def test_manifest_marked_interrupted_on_keyboard_interrupt(tmp_path, monkeypatch):
    cases = [_case("BENCH-A"), _case("BENCH-B")]
    monkeypatch.setattr(cli, "load_cases", lambda: cases)

    class _InterruptingProvider(FakeProvider):
        def generate_summary(self, prompt):
            raise KeyboardInterrupt()

    monkeypatch.setattr(cli, "build_provider", lambda name: _InterruptingProvider(name=name))
    monkeypatch.setattr(cli, "_git_metadata", lambda: (None, None))
    monkeypatch.setattr(cli, "_load_env", lambda: None)

    output_dir = tmp_path / "run"
    exit_code = cli.main(["--providers", "gemini", "--output", str(output_dir)])

    assert exit_code == 130
    manifest = json.loads((output_dir / "manifest.json").read_text())
    assert manifest["status"] == "interrupted"
    assert manifest["completed_at"] is not None
    assert manifest["result_count"] == 0


# --- predictions.jsonl / output-directory handling --------------------------


def test_prepare_output_dir_refuses_an_existing_directory(tmp_path):
    existing = tmp_path / "run"
    existing.mkdir()

    with pytest.raises(FileExistsError):
        storage.prepare_output_dir(existing)


def test_cli_fails_clearly_on_output_directory_collision(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_cases", lambda: [_case("BENCH-A")])
    monkeypatch.setattr(cli, "build_provider", lambda name: FakeProvider(name=name))
    monkeypatch.setattr(cli, "_git_metadata", lambda: (None, None))
    monkeypatch.setattr(cli, "_load_env", lambda: None)

    output_dir = tmp_path / "run"
    output_dir.mkdir()

    exit_code = cli.main(["--providers", "gemini", "--output", str(output_dir)])

    assert exit_code == 1
    assert "already exists" in capsys.readouterr().err


# --- --providers / --cases / --tags filtering --------------------------------


def test_providers_filtering_only_constructs_selected_providers(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "load_cases", lambda: [_case("BENCH-A")])
    constructed = []

    def _fake_build(name):
        constructed.append(name)
        return FakeProvider(name=name)

    monkeypatch.setattr(cli, "build_provider", _fake_build)
    monkeypatch.setattr(cli, "_git_metadata", lambda: (None, None))
    monkeypatch.setattr(cli, "_load_env", lambda: None)

    cli.main(["--providers", "medgemma", "--output", str(tmp_path / "run")])

    assert constructed == ["medgemma"]


def test_case_id_filtering():
    cases = [_case("BENCH-A"), _case("BENCH-B")]

    filtered = cli._filter_cases(cases, ["BENCH-B"], None)

    assert [case.case_id for case in filtered] == ["BENCH-B"]


def test_tag_filtering():
    cases = [_case("BENCH-A", tags=["prn"]), _case("BENCH-B", tags=["narrative_text"])]

    filtered = cli._filter_cases(cases, None, ["prn"])

    assert [case.case_id for case in filtered] == ["BENCH-A"]


def test_case_and_tag_filters_intersect():
    cases = [
        _case("BENCH-A", tags=["prn"]),
        _case("BENCH-B", tags=["prn"]),
        _case("BENCH-C", tags=["narrative_text"]),
    ]

    filtered = cli._filter_cases(cases, ["BENCH-A", "BENCH-C"], ["prn"])

    assert [case.case_id for case in filtered] == ["BENCH-A"]


def test_main_fails_clearly_when_filters_match_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_cases", lambda: [_case("BENCH-A", tags=["prn"])])

    output_dir = tmp_path / "run"
    exit_code = cli.main(["--tags", "narrative_text", "--output", str(output_dir)])

    assert exit_code == 1
    assert "No benchmark cases matched" in capsys.readouterr().err
    assert not output_dir.exists()


# --- benchmark fingerprint ----------------------------------------------------


def test_benchmark_fingerprint_is_stable_across_whitespace_only_changes():
    case_a = _case("BENCH-A")
    case_a_reformatted = _case("BENCH-A")
    case_a_reformatted.raw = json.loads(json.dumps(case_a.raw, indent=4, sort_keys=False))

    assert benchmark_fingerprint([case_a]) == benchmark_fingerprint([case_a_reformatted])


def test_benchmark_fingerprint_changes_when_case_content_changes():
    case_a = _case("BENCH-A", input_notes=["Original note text."])
    case_a_changed = _case("BENCH-A", input_notes=["Different note text."])

    assert benchmark_fingerprint([case_a]) != benchmark_fingerprint([case_a_changed])


def test_benchmark_fingerprint_is_independent_of_case_order():
    case_a, case_b = _case("BENCH-A"), _case("BENCH-B")

    assert benchmark_fingerprint([case_a, case_b]) == benchmark_fingerprint([case_b, case_a])


# --- secrets never reach artifacts -------------------------------------------


def test_no_configured_secret_appears_in_any_written_artifact(tmp_path, monkeypatch):
    # Gemini is the only provider left with a credential concept at all;
    # openbiollm/medgemma are served by a local Ollama daemon and take no
    # secret of any kind (see benchmark/runner/providers.py).
    monkeypatch.setenv("GEMINI_API_KEY", "sk-super-secret-value")
    monkeypatch.setattr(cli, "load_cases", lambda: [_case("BENCH-A")])
    monkeypatch.setattr(cli, "build_provider", lambda name: FakeProvider(name=name))
    monkeypatch.setattr(cli, "_git_metadata", lambda: (None, None))
    monkeypatch.setattr(cli, "_load_env", lambda: None)

    output_dir = tmp_path / "run"
    cli.main(["--providers", "gemini", "--output", str(output_dir)])

    manifest_text = (output_dir / "manifest.json").read_text()
    predictions_text = (output_dir / "predictions.jsonl").read_text()

    assert "sk-super-secret-value" not in manifest_text
    assert "sk-super-secret-value" not in predictions_text


# --- env loading --------------------------------------------------------------


def test_load_env_does_not_raise_when_backend_env_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "_BACKEND_ENV_PATH", tmp_path / "does-not-exist.env")

    cli._load_env()  # must not raise


def test_load_env_never_overrides_an_already_exported_credential(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "load_dotenv", lambda path, override: calls.append(override))

    cli._load_env()

    assert calls == [False]


# --- CLI argument parsing (no execution) --------------------------------------


def test_arg_parser_defaults_to_every_provider():
    args = cli.build_arg_parser().parse_args([])

    assert set(args.providers) == set(PROVIDER_NAMES)
    assert args.cases is None
    assert args.tags is None
    assert args.output is None


def test_arg_parser_rejects_an_unknown_provider():
    with pytest.raises(SystemExit):
        cli.build_arg_parser().parse_args(["--providers", "chatgpt"])


def test_arg_parser_accepts_cases_and_tags():
    args = cli.build_arg_parser().parse_args(["--cases", "BENCH-001", "BENCH-002", "--tags", "prn"])

    assert args.cases == ["BENCH-001", "BENCH-002"]
    assert args.tags == ["prn"]
