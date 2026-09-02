import logging
from dataclasses import dataclass

from pydantic import ValidationError

from app.ai.prompts import build_summary_prompt
from app.ai.providers.base import AIProvider, AIProviderError
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.medgemma_provider import MedGemmaProvider
from app.ai.providers.openbiollm_provider import OpenBioLLMProvider
from app.ai.schemas import ClinicalSummary
from app.core.config import Settings, settings

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
                "AI response failed validation (%d error(s))",
                error.error_count(),
                extra={
                    "event": "ai_response_validation_failed",
                    "provider": self._provider.name,
                    "model": self._provider.model,
                },
            )
            raise AIProviderError("AI response failed validation") from error


def build_ai_summary_service(app_settings: Settings) -> AISummaryService:
    """The single place ai_provider is ever branched on; mirrors
    app/storage/service.py's build_storage_service exactly, for the same
    reason: everywhere else in the application depends only on the
    AIProvider interface, never on this choice. Settings.ai_provider is
    validated at startup (Settings' own model_validator) to guarantee this
    function never has to raise a config error itself: the else branch
    below is unreachable in a running application, kept only as defense
    in depth.

    Taking app_settings as a parameter, rather than reading the module-
    level settings directly, is what makes this testable with a
    constructed Settings(...) instance with no monkeypatching required.
    """
    if app_settings.ai_provider == "openbiollm":
        provider: AIProvider = OpenBioLLMProvider(
            model=app_settings.openbiollm_model,
            base_url=app_settings.ollama_base_url,
        )
    elif app_settings.ai_provider == "medgemma":
        # Reuses ollama_base_url: both providers are served by the same
        # local Ollama daemon (see medgemma_provider.py), just a
        # different model tag.
        provider = MedGemmaProvider(
            model=app_settings.medgemma_model,
            base_url=app_settings.ollama_base_url,
        )
    elif app_settings.ai_provider == "gemini":
        provider = GeminiProvider(
            api_key=app_settings.gemini_api_key, model=app_settings.gemini_model
        )
    else:
        raise ValueError(f"Unsupported AI_PROVIDER: {app_settings.ai_provider!r}")

    return AISummaryService(provider)


def get_ai_summary_service() -> AISummaryService:
    """FastAPI dependency; routes declare a dependency on this function,
    never on a concrete provider class, so swapping the active provider
    is a configuration change (AI_PROVIDER), not a code change.
    """
    return build_ai_summary_service(settings)
