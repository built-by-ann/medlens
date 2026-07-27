import logging
import time

from google import genai
from google.genai import errors as genai_errors
from google.genai.types import GenerateContentConfig, HttpOptions

from app.ai.providers.base import AIProvider, AIProviderError

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.0-flash"
DEFAULT_TIMEOUT_MS = 30_000

# Constrains Gemini to emit valid JSON using the SDK's structured output
# support. This only enforces well-formed JSON, not a specific shape; the
# exact shape is described in the prompt itself (see prompts.py) and will be
# formally validated with Pydantic in a later issue. Keeping the schema out
# of this config avoids defining it twice.
JSON_RESPONSE_CONFIG = GenerateContentConfig(response_mime_type="application/json")


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(
        self,
        api_key: str | None,
        model: str = DEFAULT_MODEL,
        timeout_ms: int = DEFAULT_TIMEOUT_MS,
    ):
        self.model = model
        self._api_key = api_key
        self._timeout_ms = timeout_ms
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        # The key is checked here, not in __init__, so constructing this
        # provider (for dependency injection) always succeeds. The missing
        # key only surfaces as an AIProviderError when a summary is actually
        # requested, letting the caller handle it the same way as any other
        # provider failure.
        if not self._api_key:
            raise AIProviderError("Gemini API key is not configured")

        if self._client is None:
            self._client = genai.Client(
                api_key=self._api_key,
                http_options=HttpOptions(timeout=self._timeout_ms),
            )

        return self._client

    def generate_summary(self, prompt: str) -> str:
        started_at = time.monotonic()

        try:
            client = self._get_client()
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=JSON_RESPONSE_CONFIG,
            )
        except AIProviderError:
            raise
        except genai_errors.APIError as error:
            self._log_failure(started_at, error)
            raise AIProviderError(f"Gemini request failed: {type(error).__name__}") from error
        except Exception as error:
            self._log_failure(started_at, error)
            raise AIProviderError(
                f"Unexpected error calling Gemini: {type(error).__name__}"
            ) from error

        text = getattr(response, "text", None)

        if not text:
            self._log_failure(started_at, None, reason="empty response")
            raise AIProviderError("Gemini returned an empty or invalid response")

        duration_ms = (time.monotonic() - started_at) * 1000
        logger.info(
            "AI request succeeded provider=%s model=%s duration_ms=%.1f",
            self.name,
            self.model,
            duration_ms,
        )

        return text

    def _log_failure(
        self, started_at: float, error: Exception | None, reason: str | None = None
    ) -> None:
        duration_ms = (time.monotonic() - started_at) * 1000
        error_type = type(error).__name__ if error is not None else (reason or "unknown")

        logger.warning(
            "AI request failed provider=%s model=%s duration_ms=%.1f error_type=%s",
            self.name,
            self.model,
            duration_ms,
            error_type,
        )
