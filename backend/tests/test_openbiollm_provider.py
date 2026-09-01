import logging

import pytest
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError, ValidationError

from app.ai.providers.base import AIProviderError
from app.ai.providers.openbiollm_provider import OpenBioLLMProvider


class FakeInferenceClient:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []
        self.init_kwargs = None

    def text_generation(self, prompt, model=None, **kwargs):
        self.calls.append({"prompt": prompt, "model": model, "kwargs": kwargs})

        if self._error is not None:
            raise self._error

        return self._response


def _fake_client_factory(fake_client, captured_init_kwargs):
    def _construct(**kwargs):
        captured_init_kwargs.update(kwargs)
        return fake_client

    return _construct


class _FakeHttpResponse:
    """The minimal shape HfHubHTTPError.__init__ actually reads, a plain
    hand-written fake (this codebase avoids a mocking library, see
    docs/testing.md), not a real HTTP response.
    """

    def __init__(self):
        self.headers = {}
        self.request = None


def test_default_model_is_openbiollm_8b():
    provider = OpenBioLLMProvider(api_key="fake-key")

    assert provider.model == "aaditya/Llama3-OpenBioLLM-8B"


def test_generate_summary_raises_when_api_key_missing():
    provider = OpenBioLLMProvider(api_key=None)

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_does_not_construct_client_when_key_missing(monkeypatch):
    def _unexpected_client(**kwargs):
        raise AssertionError("InferenceClient should not be constructed without an api key")

    monkeypatch.setattr("app.ai.providers.openbiollm_provider.InferenceClient", _unexpected_client)

    provider = OpenBioLLMProvider(api_key=None)

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_returns_text_on_success(monkeypatch):
    fake_client = FakeInferenceClient(response='{"medications": []}')
    init_kwargs = {}
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, init_kwargs),
    )

    provider = OpenBioLLMProvider(api_key="fake-key", model="openbiollm-test")
    result = provider.generate_summary("some prompt")

    assert result == '{"medications": []}'
    assert len(fake_client.calls) == 1
    assert fake_client.calls[0]["prompt"] == "some prompt"


def test_generate_summary_passes_the_configured_model(monkeypatch):
    fake_client = FakeInferenceClient(response="{}")
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key", model="aaditya/Llama3-OpenBioLLM-8B")
    provider.generate_summary("some prompt")

    assert fake_client.calls[0]["model"] == "aaditya/Llama3-OpenBioLLM-8B"


def test_client_is_constructed_with_the_pinned_featherless_ai_provider(monkeypatch):
    # Reproducibility requirement: provider="featherless-ai" is pinned
    # explicitly, never "auto"; see openbiollm_provider.py's own comment
    # for why. This test fails if that pin is ever accidentally removed.
    fake_client = FakeInferenceClient(response="{}")
    init_kwargs = {}
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, init_kwargs),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")
    provider.generate_summary("some prompt")

    assert init_kwargs["provider"] == "featherless-ai"
    assert init_kwargs["token"] == "fake-key"


def test_generate_summary_uses_deterministic_generation_parameters(monkeypatch):
    fake_client = FakeInferenceClient(response="{}")
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")
    provider.generate_summary("some prompt")

    kwargs = fake_client.calls[0]["kwargs"]
    assert kwargs["do_sample"] is False
    assert kwargs["return_full_text"] is False
    assert kwargs["max_new_tokens"] > 0


def test_generate_summary_wraps_timeout_error(monkeypatch):
    fake_client = FakeInferenceClient(error=InferenceTimeoutError("timed out"))
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_wraps_validation_error(monkeypatch):
    fake_client = FakeInferenceClient(error=ValidationError("invalid generation parameters"))
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_wraps_http_error(monkeypatch):
    error = HfHubHTTPError("503 Server Error", response=_FakeHttpResponse())
    fake_client = FakeInferenceClient(error=error)
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_wraps_unexpected_exception(monkeypatch):
    fake_client = FakeInferenceClient(error=RuntimeError("connection reset"))
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_logs_failure_detail_server_side_only(monkeypatch, caplog):
    fake_client = FakeInferenceClient(error=RuntimeError("connection reset"))
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")

    with caplog.at_level(logging.WARNING), pytest.raises(AIProviderError) as exc_info:
        provider.generate_summary("some prompt")

    assert "connection reset" in caplog.text
    (record,) = [r for r in caplog.records if r.event == "ai_request_failed"]
    assert record.error_type == "RuntimeError"
    assert record.provider == "openbiollm"
    # The failure detail is server-side-log-only; it must never reach the
    # caller (see _safe_error_message, app/api/routes/analyses.py), which
    # only ever sees the generic wrapped message below.
    assert "connection reset" not in str(exc_info.value)
    assert str(exc_info.value) == "Unexpected error calling OpenBioLLM: RuntimeError"


def test_generate_summary_raises_on_empty_response(monkeypatch):
    fake_client = FakeInferenceClient(response="")
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_logs_duration_ms_on_success(monkeypatch, caplog):
    fake_client = FakeInferenceClient(response="{}")
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")

    with caplog.at_level(logging.INFO):
        provider.generate_summary("some prompt")

    (record,) = [r for r in caplog.records if r.event == "ai_request_succeeded"]
    assert isinstance(record.duration_ms, float)
    assert record.duration_ms >= 0
    assert record.provider == "openbiollm"


# --- Output cleanup: strictly syntactic, never a JSON repair layer ------
#
# Per this issue's explicit boundary: cleanup may strip markdown fences
# and surrounding prose around an otherwise-intact JSON object, and must
# never repair, complete, or otherwise alter the JSON's own content.
# AISummaryService._parse_response (ClinicalSummary.model_validate_json)
# remains the only thing that validates the result; these tests only
# check what string this provider hands back to it.


def test_strips_markdown_json_code_fence(monkeypatch):
    fenced = '```json\n{"medications": [], "possible_inconsistencies": [], "summary": "ok"}\n```'
    fake_client = FakeInferenceClient(response=fenced)
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")
    result = provider.generate_summary("some prompt")

    assert result == '{"medications": [], "possible_inconsistencies": [], "summary": "ok"}'


def test_strips_bare_code_fence_without_json_language_tag(monkeypatch):
    fenced = '```\n{"medications": []}\n```'
    fake_client = FakeInferenceClient(response=fenced)
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")
    result = provider.generate_summary("some prompt")

    assert result == '{"medications": []}'


def test_strips_surrounding_prose_around_the_json_object(monkeypatch):
    wrapped = (
        "Here is the extracted medication information:\n"
        '{"medications": [], "possible_inconsistencies": [], "summary": "ok"}\n'
        "Let me know if you need anything else."
    )
    fake_client = FakeInferenceClient(response=wrapped)
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")
    result = provider.generate_summary("some prompt")

    assert result == '{"medications": [], "possible_inconsistencies": [], "summary": "ok"}'


def test_strips_prose_and_fence_together(monkeypatch):
    wrapped = 'Sure, here\'s the JSON:\n```json\n{"medications": []}\n```\nHope that helps!'
    fake_client = FakeInferenceClient(response=wrapped)
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")
    result = provider.generate_summary("some prompt")

    assert result == '{"medications": []}'


def test_does_not_repair_malformed_json_inside_a_fence(monkeypatch):
    # Deliberately broken: an unbalanced bracket. Cleanup must not notice
    # or fix this; only AISummaryService's real validation should ever
    # reject it.
    broken = '```json\n{"medications": [}\n```'
    fake_client = FakeInferenceClient(response=broken)
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")
    result = provider.generate_summary("some prompt")

    assert result == '{"medications": [}'

    import json

    with pytest.raises(json.JSONDecodeError):
        json.loads(result)


def test_does_not_repair_malformed_json_with_missing_closing_brace(monkeypatch):
    broken = 'Here is the result:\n{"medications": [], "summary": "ok"'
    fake_client = FakeInferenceClient(response=broken)
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")
    result = provider.generate_summary("some prompt")

    # No closing brace exists anywhere in the raw text, so the boundary-
    # finding cleanup can't identify where the JSON object would end; it
    # falls back to returning the text unchanged rather than guessing a
    # boundary or inventing a closing brace. The leading prose is *not*
    # stripped in this case; this is the deliberately conservative,
    # never-guess behavior, not a bug.
    assert result == broken

    import json

    with pytest.raises(json.JSONDecodeError):
        json.loads(result)


def test_does_not_alter_field_content_inside_the_json_object(monkeypatch):
    # A cleanup step that touched field content, rather than only the
    # text surrounding the object, would be exactly the "hidden repair
    # layer" this issue explicitly forbids; this test pins the entire
    # object byte-for-byte, not just that it parses.
    payload = (
        '{"medications": [{"name": "Lisinopril", "dosage": "10 mg", "route": null, '
        '"frequency": null, "status": null, "notes": null, "source_note": 1}], '
        '"possible_inconsistencies": [], "summary": "Patient takes Lisinopril."}'
    )
    fenced = f"```json\n{payload}\n```"
    fake_client = FakeInferenceClient(response=fenced)
    monkeypatch.setattr(
        "app.ai.providers.openbiollm_provider.InferenceClient",
        _fake_client_factory(fake_client, {}),
    )

    provider = OpenBioLLMProvider(api_key="fake-key")
    result = provider.generate_summary("some prompt")

    assert result == payload
