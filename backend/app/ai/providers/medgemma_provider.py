import logging
import time

from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError, ValidationError

from app.ai.providers.base import AIProvider, AIProviderError
from app.ai.providers.text_cleanup import extract_json_object, strip_code_fences

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "google/medgemma-27b-text-it"

# The one Hugging Face Inference Provider currently serving this exact
# checkpoint, verified directly against Hugging Face's own API while
# implementing this issue:
#
#   GET https://huggingface.co/api/models/google/medgemma-27b-text-it
#       ?expand[]=inferenceProviderMapping
#   -> {"featherless-ai": {"status": "live", "task": "conversational", ...}}
#
# It's the only MedGemma checkpoint with any live Inference Provider at
# all: both 4B checkpoints (the original and 1.5) are multimodal and
# currently have no provider serving them ("This model isn't deployed by
# any Inference Provider", per their own model pages), which is why this
# text-only 27B checkpoint is the one integrated here rather than a 4B
# variant, despite being larger. See docs/ai.md for the full reasoning.
#
# Pinned explicitly rather than provider="auto", for the same
# reproducibility reason OpenBioLLMProvider pins its own provider (see
# openbiollm_provider.py): "auto" could silently resolve to a different
# backend if Hugging Face's provider landscape changes, which would be a
# real problem for #89's benchmark reproducibility.
INFERENCE_PROVIDER = "featherless-ai"

# Unlike OpenBioLLM (task "text-generation", called via text_generation()),
# this checkpoint's only live provider mapping is task "conversational" -
# it's served through Hugging Face's chat-completion mechanism, not plain
# text completion. AIProvider.generate_summary(prompt: str) -> str does
# not change: this provider internally wraps the single prompt string
# build_summary_prompt() (app/ai/prompts.py) already produces into one
# user-turn message before calling chat_completion(), the same way
# GeminiProvider wraps it as contents=prompt and OpenBioLLMProvider wraps
# it as inputs=prompt. build_summary_prompt() itself is unchanged.
DEFAULT_TIMEOUT_S = 30.0

# Generation parameters for MedGemmaProvider, chosen for structured
# extraction rather than open-ended conversation. Kept as constants here
# (not Settings/.env), mirroring OpenBioLLMProvider.GENERATION_PARAMS -
# these describe how this one provider is called, not deployment
# configuration.
#
# #89's evaluation framework should record these exact values alongside
# any benchmark results run against this provider, since changing them
# would change what's actually being measured.
GENERATION_PARAMS = {
    # temperature=0 is the closest thing to deterministic, greedy
    # decoding the chat-completion API exposes (there is no do_sample
    # equivalent for this task type, unlike OpenBioLLM's
    # text_generation()). top_p is deliberately left unset: it only
    # affects sampling, which a temperature of 0 already eliminates.
    "temperature": 0,
    # Large enough to hold a full ClinicalSummary JSON response (a
    # medications list, possible_inconsistencies, and a summary) for a
    # multi-document, multi-medication analysis without truncating
    # mid-object. Not tuned empirically; a conservative upper bound,
    # matching OpenBioLLMProvider's own max_new_tokens.
    "max_tokens": 1024,
}


class MedGemmaProvider(AIProvider):
    """MedGemma (google/medgemma-27b-text-it), called through Hugging
    Face's hosted Inference Providers, no local model weights, and no
    torch/transformers/accelerate in this application at all. See the
    module comments above for the exact provider, task, and generation
    configuration, verified while implementing this issue.

    Deliberately does not use response_format/schema-constrained
    generation: #89's benchmark needs to measure this model's actual,
    unassisted ability to produce the requested JSON shape, the same
    reasoning already applied to OpenBioLLMProvider. Output cleanup is
    therefore strictly syntactic (see app/ai/providers/text_cleanup.py);
    never a hidden repair layer.

    Requires the Hugging Face account behind HUGGINGFACE_API_KEY to have
    accepted Google's "Health AI Developer Foundations" license terms for
    this gated model; MedLens itself performs no license-acceptance
    logic of its own (see docs/ai.md's setup prerequisites).
    """

    name = "medgemma"

    def __init__(
        self,
        api_key: str | None,
        model: str = DEFAULT_MODEL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ):
        self.model = model
        self._api_key = api_key
        self._timeout_s = timeout_s
        self._client: InferenceClient | None = None

    def _get_client(self) -> InferenceClient:
        # The key is checked here, not in __init__, so constructing this
        # provider (for dependency injection) always succeeds; mirrors
        # GeminiProvider._get_client and OpenBioLLMProvider._get_client
        # exactly, for the same reason: the missing-credential case
        # should surface as an AIProviderError only when a summary is
        # actually requested.
        if not self._api_key:
            raise AIProviderError("Hugging Face API key is not configured")

        if self._client is None:
            self._client = InferenceClient(
                provider=INFERENCE_PROVIDER,
                token=self._api_key,
                timeout=self._timeout_s,
            )

        return self._client

    def generate_summary(self, prompt: str) -> str:
        started_at = time.monotonic()

        try:
            client = self._get_client()
            response = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                **GENERATION_PARAMS,
            )
        except AIProviderError:
            raise
        except (InferenceTimeoutError, HfHubHTTPError, ValidationError) as error:
            self._log_failure(started_at, error)
            raise AIProviderError(f"MedGemma request failed: {type(error).__name__}") from error
        except Exception as error:
            self._log_failure(started_at, error)
            raise AIProviderError(
                f"Unexpected error calling MedGemma: {type(error).__name__}"
            ) from error

        raw_text = self._extract_message_content(response)

        if not raw_text:
            self._log_failure(started_at, None, reason="empty response")
            raise AIProviderError("MedGemma returned an empty or invalid response")

        # Strictly syntactic cleanup only; see text_cleanup.py's own
        # docstrings. Never repairs, never touches field content.
        # AISummaryService._parse_response is still the only thing that
        # validates the result against ClinicalSummary.
        cleaned_text = extract_json_object(strip_code_fences(raw_text))

        duration_ms = (time.monotonic() - started_at) * 1000
        logger.info(
            "AI request succeeded",
            extra={
                "event": "ai_request_succeeded",
                "provider": self.name,
                "model": self.model,
                "duration_ms": round(duration_ms, 1),
            },
        )

        return cleaned_text

    @staticmethod
    def _extract_message_content(response: object) -> str | None:
        """Pulls the assistant's message text out of a ChatCompletionOutput.

        A missing/empty choices list, or a message with no content, is
        treated the same way GeminiProvider/OpenBioLLMProvider already
        treat an empty raw response, as "no usable content" (raised by
        the caller as an AIProviderError), never a crash or a guess at
        what the model meant to say.
        """
        choices = getattr(response, "choices", None)
        if not choices:
            return None

        message = getattr(choices[0], "message", None)
        return getattr(message, "content", None)

    def _log_failure(
        self, started_at: float, error: Exception | None, reason: str | None = None
    ) -> None:
        duration_ms = (time.monotonic() - started_at) * 1000
        error_type = type(error).__name__ if error is not None else (reason or "unknown")
        detail = self._error_detail(error, reason)

        # Same split as GeminiProvider._log_failure/OpenBioLLMProvider.
        # _log_failure: detail is server-side log only, never included in
        # the AIProviderError message raised above (which is what
        # _safe_error_message, app/api/routes/analyses.py, lets reach the
        # frontend). The Hugging Face token is sent as a request header,
        # never in a URL or exception message, and neither the prompt nor
        # any clinical text is ever passed to this method or logged
        # anywhere.
        logger.warning(
            "AI request failed: %s",
            detail,
            extra={
                "event": "ai_request_failed",
                "provider": self.name,
                "model": self.model,
                "duration_ms": round(duration_ms, 1),
                "error_type": error_type,
            },
        )

    @staticmethod
    def _error_detail(error: Exception | None, reason: str | None) -> str:
        if error is None:
            return reason or "unknown"

        return str(error)
