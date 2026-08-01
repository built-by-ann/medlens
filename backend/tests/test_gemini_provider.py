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


def test_generate_summary_wraps_unexpected_exception(monkeypatch):
    fake_models = FakeModels(error=RuntimeError("connection reset"))
    monkeypatch.setattr(
        "app.ai.providers.gemini_provider.genai.Client",
        lambda **kwargs: FakeClient(fake_models),
    )

    provider = GeminiProvider(api_key="fake-key")

    with pytest.raises(AIProviderError):
        provider.generate_summary("some prompt")


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
