import logging
from dataclasses import dataclass

from pydantic import ValidationError

from app.ai.prompts import build_summary_prompt
from app.ai.providers.base import AIProvider, AIProviderError
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.schemas import ClinicalSummary
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AISummaryResult:
    provider: str
    model: str
    clinical_summary: ClinicalSummary


class AISummaryService:
    """Combines clinical notes into a prompt and delegates to a provider.

    Depends only on the AIProvider interface, not on any specific provider
    implementation, so a different provider can be substituted (for testing,
    or for a future provider) without changing this class.

    The provider is responsible only for communicating with the model and
    returning its raw text response. Parsing that text into a validated
    ClinicalSummary, and rejecting anything that does not match, is this
    service's responsibility.
    """

    def __init__(self, provider: AIProvider):
        self._provider = provider

    def summarize(self, clinical_notes: list[str]) -> AISummaryResult:
        prompt = build_summary_prompt(clinical_notes)
        raw_response = self._provider.generate_summary(prompt)

        clinical_summary = self._parse_response(raw_response)

        return AISummaryResult(
            provider=self._provider.name,
            model=self._provider.model,
            clinical_summary=clinical_summary,
        )

    def _parse_response(self, raw_response: str) -> ClinicalSummary:
        try:
            return ClinicalSummary.model_validate_json(raw_response)
        except ValidationError as error:
            # error.errors() can include fragments of the offending input,
            # which may echo clinical note content back through the model's
            # response, so only a count is logged, never the errors or the
            # raw response itself.
            logger.warning(
                "AI response failed validation provider=%s model=%s error_count=%d",
                self._provider.name,
                self._provider.model,
                error.error_count(),
            )
            raise AIProviderError("AI response failed validation") from error


def get_ai_summary_service() -> AISummaryService:
    provider = GeminiProvider(api_key=settings.gemini_api_key, model=settings.gemini_model)

    return AISummaryService(provider)
