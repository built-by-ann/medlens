import io
import json
import logging
import urllib.error

import pytest

from app.ai.providers.base import AIProviderError
from app.ai.providers.openbiollm_provider import OpenBioLLMProvider


class _FakeHTTPResponse:
    """The minimal shape urlopen()'s caller reads: a context manager whose
    .read() returns the response body bytes. A plain hand-written fake
    (this codebase avoids a mocking library, see docs/testing.md), not a
    real HTTP response.
    """

    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _fake_urlopen(response_body=None, error=None, calls=None):
    """Replaces urllib.request.urlopen for the duration of one test.
    `calls`, if given, collects the raw Request object from every call so
    a test can inspect exactly what was sent (URL, headers, body).
    """

    def _urlopen(request, timeout=None):
        if calls is not None:
            calls.append(request)
        if error is not None:
            raise error
        return _FakeHTTPResponse(json.dumps(response_body).encode("utf-8"))

    return _urlopen


def _http_error(code: int, body: dict | bytes = b"{}") -> urllib.error.HTTPError:
    fp = io.BytesIO(body if isinstance(body, bytes) else json.dumps(body).encode("utf-8"))
    return urllib.error.HTTPError(
        url="http://localhost:11434/api/chat", code=code, msg="error", hdrs=None, fp=fp
    )


def _sent_payload(request) -> dict:
    return json.loads(request.data)


def test_default_model_is_the_local_llama3_instruct_templated_model():
    provider = OpenBioLLMProvider()

    assert provider.model == "openbiollm-llama3-instruct"


def test_default_base_url_is_localhost_ollama():
    provider = OpenBioLLMProvider()

    assert provider.base_url == "http://localhost:11434"


def test_generate_summary_returns_text_on_success(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(
            response_body={"message": {"role": "assistant", "content": '{"medications": []}'}},
            calls=calls,
        ),
    )

    provider = OpenBioLLMProvider(model="openbiollm-test")
    result = provider.generate_summary("some prompt")

    assert result == '{"medications": []}'
    assert len(calls) == 1


def test_generate_summary_sends_the_prompt_as_a_single_user_message(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": "{}"}}, calls=calls),
    )

    provider = OpenBioLLMProvider()
    provider.generate_summary("extract medications from this note")

    payload = _sent_payload(calls[0])
    assert payload["messages"] == [
        {"role": "user", "content": "extract medications from this note"}
    ]


def test_generate_summary_calls_the_configured_model_via_the_chat_endpoint(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": "{}"}}, calls=calls),
    )

    provider = OpenBioLLMProvider(
        model="openbiollm-llama3-instruct", base_url="http://localhost:11434"
    )
    provider.generate_summary("some prompt")

    request = calls[0]
    # /api/chat, not /api/generate: this is what applies the target
    # model's own chat template automatically. See the module docstring
    # for why this matters specifically for OpenBioLLM.
    assert request.full_url == "http://localhost:11434/api/chat"
    payload = _sent_payload(request)
    assert payload["model"] == "openbiollm-llama3-instruct"
    assert payload["stream"] is False


def test_generate_summary_uses_deterministic_generation_parameters(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": "{}"}}, calls=calls),
    )

    provider = OpenBioLLMProvider()
    provider.generate_summary("some prompt")

    options = _sent_payload(calls[0])["options"]
    assert options["temperature"] == 0
    assert options["seed"] == 0
    assert options["num_predict"] > 0


def test_generate_summary_never_requests_json_constrained_generation(monkeypatch):
    # #90's benchmark measures this model's own, unassisted ability to
    # produce the requested JSON shape; Ollama's `format: "json"` option
    # must never be sent, deliberately, or that's no longer being
    # measured. See the module's own GENERATION_PARAMS comment.
    calls = []
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": "{}"}}, calls=calls),
    )

    provider = OpenBioLLMProvider()
    provider.generate_summary("some prompt")

    assert "format" not in _sent_payload(calls[0])


def test_generate_summary_raises_a_clear_error_when_ollama_is_unreachable(monkeypatch):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(error=urllib.error.URLError(ConnectionRefusedError("refused"))),
    )

    provider = OpenBioLLMProvider(base_url="http://localhost:11434")

    with pytest.raises(AIProviderError, match="Could not connect to Ollama"):
        provider.generate_summary("some prompt")


def test_generate_summary_raises_a_clear_error_when_the_model_is_not_installed(monkeypatch):
    error = _http_error(
        404, {"error": "model 'openbiollm-llama3-instruct' not found, try pulling it first"}
    )
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(error=error))

    provider = OpenBioLLMProvider(model="openbiollm-llama3-instruct")

    with pytest.raises(AIProviderError, match="is not installed"):
        provider.generate_summary("some prompt")


def test_generate_summary_wraps_a_bare_timeout(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(error=TimeoutError("timed out")))

    provider = OpenBioLLMProvider()

    with pytest.raises(AIProviderError, match="timed out"):
        provider.generate_summary("some prompt")


def test_generate_summary_wraps_a_urlerror_carrying_a_timeout(monkeypatch):
    # The connection-phase equivalent of a bare TimeoutError; both must be
    # recognized as a timeout, not a generic connection failure.
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(error=urllib.error.URLError(TimeoutError("timed out"))),
    )

    provider = OpenBioLLMProvider()

    with pytest.raises(AIProviderError, match="timed out"):
        provider.generate_summary("some prompt")


def test_generate_summary_wraps_an_unexpected_http_error(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(error=_http_error(500)))

    provider = OpenBioLLMProvider()

    with pytest.raises(AIProviderError, match="HTTP 500"):
        provider.generate_summary("some prompt")


def test_generate_summary_wraps_unexpected_exception(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(error=RuntimeError("boom")))

    provider = OpenBioLLMProvider()

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_logs_failure_detail_server_side_only(monkeypatch, caplog):
    monkeypatch.setattr(
        "urllib.request.urlopen", _fake_urlopen(error=RuntimeError("connection reset"))
    )

    provider = OpenBioLLMProvider()

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
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": ""}}),
    )

    provider = OpenBioLLMProvider()

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_raises_on_missing_message_key(monkeypatch):
    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen(response_body={}))

    provider = OpenBioLLMProvider()

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_logs_duration_ms_on_success(monkeypatch, caplog):
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": "{}"}}),
    )

    provider = OpenBioLLMProvider()

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
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": fenced}}),
    )

    provider = OpenBioLLMProvider()
    result = provider.generate_summary("some prompt")

    assert result == '{"medications": [], "possible_inconsistencies": [], "summary": "ok"}'


def test_strips_bare_code_fence_without_json_language_tag(monkeypatch):
    fenced = '```\n{"medications": []}\n```'
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": fenced}}),
    )

    provider = OpenBioLLMProvider()
    result = provider.generate_summary("some prompt")

    assert result == '{"medications": []}'


def test_strips_surrounding_prose_around_the_json_object(monkeypatch):
    wrapped = (
        "Here is the extracted medication information:\n"
        '{"medications": [], "possible_inconsistencies": [], "summary": "ok"}\n'
        "Let me know if you need anything else."
    )
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": wrapped}}),
    )

    provider = OpenBioLLMProvider()
    result = provider.generate_summary("some prompt")

    assert result == '{"medications": [], "possible_inconsistencies": [], "summary": "ok"}'


def test_strips_prose_and_fence_together(monkeypatch):
    wrapped = 'Sure, here\'s the JSON:\n```json\n{"medications": []}\n```\nHope that helps!'
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": wrapped}}),
    )

    provider = OpenBioLLMProvider()
    result = provider.generate_summary("some prompt")

    assert result == '{"medications": []}'


def test_does_not_repair_malformed_json_inside_a_fence(monkeypatch):
    # Deliberately broken: an unbalanced bracket. Cleanup must not notice
    # or fix this; only AISummaryService's real validation should ever
    # reject it.
    broken = '```json\n{"medications": [}\n```'
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": broken}}),
    )

    provider = OpenBioLLMProvider()
    result = provider.generate_summary("some prompt")

    assert result == '{"medications": [}'

    with pytest.raises(json.JSONDecodeError):
        json.loads(result)


def test_does_not_repair_malformed_json_with_missing_closing_brace(monkeypatch):
    broken = 'Here is the result:\n{"medications": [], "summary": "ok"'
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": broken}}),
    )

    provider = OpenBioLLMProvider()
    result = provider.generate_summary("some prompt")

    # No closing brace exists anywhere in the raw text, so the boundary-
    # finding cleanup can't identify where the JSON object would end; it
    # falls back to returning the text unchanged rather than guessing a
    # boundary or inventing a closing brace. The leading prose is *not*
    # stripped in this case; this is the deliberately conservative,
    # never-guess behavior, not a bug.
    assert result == broken

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
    monkeypatch.setattr(
        "urllib.request.urlopen",
        _fake_urlopen(response_body={"message": {"content": fenced}}),
    )

    provider = OpenBioLLMProvider()
    result = provider.generate_summary("some prompt")

    assert result == payload
