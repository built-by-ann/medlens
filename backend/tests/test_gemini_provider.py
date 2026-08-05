import logging

import pytest
from google.genai import errors as genai_errors

from app.ai.providers.base import AIProviderError
from app.ai.providers.gemini_provider import GeminiProvider


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeModels:
    def __init__(self, response=None, error=None):
        self._response = response
        self._error = error
        self.calls = []

    def generate_content(self, model, contents, config=None):
        self.calls.append((model, contents, config))

        if self._error is not None:
            raise self._error

        return self._response


class FakeClient:
    def __init__(self, models):
        self.models = models


def test_default_model_is_gemini_2_5_flash():
    provider = GeminiProvider(api_key="fake-key")

    assert provider.model == "gemini-2.5-flash"


def test_generate_summary_raises_when_api_key_missing():
    provider = GeminiProvider(api_key=None)

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_does_not_construct_client_when_key_missing(monkeypatch):
    def _unexpected_client(**kwargs):
        raise AssertionError("Client should not be constructed without an api key")

    monkeypatch.setattr("app.ai.providers.gemini_provider.genai.Client", _unexpected_client)

    provider = GeminiProvider(api_key=None)

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_returns_text_on_success(monkeypatch):
    fake_models = FakeModels(response=FakeResponse("Concise medication summary."))
    monkeypatch.setattr(
        "app.ai.providers.gemini_provider.genai.Client",
        lambda **kwargs: FakeClient(fake_models),
    )

    provider = GeminiProvider(api_key="fake-key", model="gemini-test")
    result = provider.generate_summary("some prompt")

    assert result == "Concise medication summary."
    assert len(fake_models.calls) == 1
    model, contents, _config = fake_models.calls[0]
    assert model == "gemini-test"
    assert contents == "some prompt"


def test_generate_summary_requests_json_response_mime_type(monkeypatch):
    fake_models = FakeModels(response=FakeResponse("{}"))
    monkeypatch.setattr(
        "app.ai.providers.gemini_provider.genai.Client",
        lambda **kwargs: FakeClient(fake_models),
    )

    provider = GeminiProvider(api_key="fake-key")
    provider.generate_summary("some prompt")

    _, _, config = fake_models.calls[0]
    assert config is not None
    assert config.response_mime_type == "application/json"


def test_generate_summary_wraps_api_error(monkeypatch):
    fake_models = FakeModels(error=genai_errors.ClientError(400, {"message": "bad request"}, None))
    monkeypatch.setattr(
        "app.ai.providers.gemini_provider.genai.Client",
        lambda **kwargs: FakeClient(fake_models),
    )

    provider = GeminiProvider(api_key="fake-key")

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_logs_api_error_message_server_side_only(monkeypatch, caplog):
    # 404 "model not found" is the real shape of the production incident
    # this logging change was made for: the model in DEFAULT_MODEL/
    # GEMINI_MODEL retired server-side, and the only thing the previous log
    # line recorded was error_type=ClientError - not enough to diagnose
    # without reproducing the request by hand.
    fake_models = FakeModels(
        error=genai_errors.ClientError(
            404, {"message": "models/gemini-2.0-flash is not found", "status": "NOT_FOUND"}, None
        )
    )
    monkeypatch.setattr(
        "app.ai.providers.gemini_provider.genai.Client",
        lambda **kwargs: FakeClient(fake_models),
    )

    provider = GeminiProvider(api_key="fake-key")

    with caplog.at_level(logging.WARNING), pytest.raises(AIProviderError) as exc_info:
        provider.generate_summary("some prompt")

    assert "models/gemini-2.0-flash is not found" in caplog.text
    # error_type is a structured field (extra=), not part of the message
    # text caplog.text renders - see app/core/logging_config.py's
    # ALLOWED_FIELDS/JSONFormatter for why call sites pass fields this way
    # rather than baking them into the message string.
    (record,) = [r for r in caplog.records if r.event == "ai_request_failed"]
    assert record.error_type == "ClientError"
    assert record.provider == "gemini"
    # The API's failure description is server-side-log-only - it must never
    # reach the caller (see _safe_error_message, app/api/routes/analyses.py),
    # which only ever sees the generic wrapped message below.
    assert "models/gemini-2.0-flash is not found" not in str(exc_info.value)
    assert str(exc_info.value) == "Gemini request failed: ClientError"


def test_generate_summary_wraps_unexpected_exception(monkeypatch):
    fake_models = FakeModels(error=RuntimeError("connection reset"))
    monkeypatch.setattr(
        "app.ai.providers.gemini_provider.genai.Client",
        lambda **kwargs: FakeClient(fake_models),
    )

    provider = GeminiProvider(api_key="fake-key")

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_logs_unexpected_exception_message_server_side_only(monkeypatch, caplog):
    fake_models = FakeModels(error=RuntimeError("connection reset"))
    monkeypatch.setattr(
        "app.ai.providers.gemini_provider.genai.Client",
        lambda **kwargs: FakeClient(fake_models),
    )

    provider = GeminiProvider(api_key="fake-key")

    with caplog.at_level(logging.WARNING), pytest.raises(AIProviderError) as exc_info:
        provider.generate_summary("some prompt")

    assert "connection reset" in caplog.text
    assert "connection reset" not in str(exc_info.value)


def test_generate_summary_raises_on_empty_response(monkeypatch):
    fake_models = FakeModels(response=FakeResponse(""))
    monkeypatch.setattr(
        "app.ai.providers.gemini_provider.genai.Client",
        lambda **kwargs: FakeClient(fake_models),
    )

    provider = GeminiProvider(api_key="fake-key")

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


def test_generate_summary_raises_on_none_response_text(monkeypatch):
    fake_models = FakeModels(response=FakeResponse(None))
    monkeypatch.setattr(
        "app.ai.providers.gemini_provider.genai.Client",
        lambda **kwargs: FakeClient(fake_models),
    )

    provider = GeminiProvider(api_key="fake-key")

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


# --- Timing (Issue #60) -------------------------------------------------
#
# duration_ms on ai_request_succeeded/ai_request_failed already existed
# before this issue (added when this file's other logging assertions were
# written, Issue #59) - these two tests are new *coverage* for that
# already-correct behavior, not a code change, per Issue #60's own
# "Leverage existing request timing... avoid duplicated instrumentation."


def test_generate_summary_logs_duration_ms_on_success(monkeypatch, caplog):
    fake_models = FakeModels(response=FakeResponse("Concise medication summary."))
    monkeypatch.setattr(
        "app.ai.providers.gemini_provider.genai.Client",
        lambda **kwargs: FakeClient(fake_models),
    )

    provider = GeminiProvider(api_key="fake-key", model="gemini-test")

    with caplog.at_level(logging.INFO):
        provider.generate_summary("some prompt")

    (record,) = [r for r in caplog.records if r.event == "ai_request_succeeded"]
    assert isinstance(record.duration_ms, float)
    assert record.duration_ms >= 0
    assert record.provider == "gemini"
    assert record.model == "gemini-test"


def test_generate_summary_logs_duration_ms_on_failure(monkeypatch, caplog):
    fake_models = FakeModels(error=RuntimeError("connection reset"))
    monkeypatch.setattr(
        "app.ai.providers.gemini_provider.genai.Client",
        lambda **kwargs: FakeClient(fake_models),
    )

    provider = GeminiProvider(api_key="fake-key")

    with caplog.at_level(logging.WARNING), pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")

    (record,) = [r for r in caplog.records if r.event == "ai_request_failed"]
    assert isinstance(record.duration_ms, float)
    assert record.duration_ms >= 0


def test_generate_summary_reuses_client_across_calls(monkeypatch):
    fake_models = FakeModels(response=FakeResponse("Summary."))
    construction_count = {"count": 0}

    def _fake_client(**kwargs):
        construction_count["count"] += 1
        return FakeClient(fake_models)

    monkeypatch.setattr("app.ai.providers.gemini_provider.genai.Client", _fake_client)

    provider = GeminiProvider(api_key="fake-key")
    provider.generate_summary("first prompt")
    provider.generate_summary("second prompt")

    assert construction_count["count"] == 1
