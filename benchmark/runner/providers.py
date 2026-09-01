"""Provider registry for the evaluation runner (Issue #89).

Maps a CLI-facing provider name to the real, production AIProvider class
and the environment variable holding its credential - the same three
classes, and the same env var names, build_ai_summary_service() (app/ai/
service.py) already uses, just constructed directly rather than through
Settings/build_ai_summary_service()/get_ai_summary_service(). The
evaluation runner needs several providers active in one process, which
AI_PROVIDER's single-active-provider design isn't suited for; constructing
Settings at all would also require DATABASE_URL/JWT_SECRET_KEY, which have
nothing to do with evaluation - see benchmark/README.md for the full
reasoning.

Deliberately a plain mapping, not a factory class: all three providers
share one constructor shape (api_key, optional model, optional timeout),
so nothing more than a dict is needed to select between them.
"""

from __future__ import annotations

import os

from app.ai.providers import medgemma_provider, openbiollm_provider
from app.ai.providers.base import AIProvider
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.medgemma_provider import MedGemmaProvider
from app.ai.providers.openbiollm_provider import OpenBioLLMProvider

# name -> (AIProvider subclass, environment variable holding its credential).
# Order here is the default --providers order (see cli.py).
PROVIDER_REGISTRY: dict[str, tuple[type[AIProvider], str]] = {
    "gemini": (GeminiProvider, "GEMINI_API_KEY"),
    "openbiollm": (OpenBioLLMProvider, "HUGGINGFACE_API_KEY"),
    "medgemma": (MedGemmaProvider, "HUGGINGFACE_API_KEY"),
}

PROVIDER_NAMES: tuple[str, ...] = tuple(PROVIDER_REGISTRY.keys())


def build_provider(name: str) -> AIProvider:
    """Constructs the named provider directly, reading its credential from
    the process environment (already best-effort loaded from backend/.env
    by cli.py's _load_env()) - no Settings instance, no database/JWT
    configuration required. Uses each provider's own default model
    (DEFAULT_MODEL in its own module); never a duplicated literal here.
    """
    try:
        provider_cls, env_var = PROVIDER_REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown provider: {name!r}. Known providers: {', '.join(PROVIDER_NAMES)}"
        ) from None

    return provider_cls(api_key=os.environ.get(env_var))


def inference_backend_for(provider: AIProvider) -> str | None:
    """The Hugging Face Inference Provider a given AIProvider instance is
    actually served through, if any - None for GeminiProvider (no such
    concept applies to it). Read from each provider module's own
    INFERENCE_PROVIDER constant rather than hardcoded here, so a future
    pin change (see openbiollm_provider.py/medgemma_provider.py's own
    reproducibility comments) is reflected automatically.
    """
    if isinstance(provider, OpenBioLLMProvider):
        return openbiollm_provider.INFERENCE_PROVIDER
    if isinstance(provider, MedGemmaProvider):
        return medgemma_provider.INFERENCE_PROVIDER
    return None


def generation_params_for(provider: AIProvider) -> dict:
    """The hardcoded GENERATION_PARAMS constant for a provider that has
    one, copied (never the module's own dict, so a caller mutating the
    result can't affect the real constant) - {} for GeminiProvider, which
    has no equivalent parameter dict (its only generation configuration,
    JSON_RESPONSE_CONFIG, isn't in this shape).
    """
    if isinstance(provider, OpenBioLLMProvider):
        return dict(openbiollm_provider.GENERATION_PARAMS)
    if isinstance(provider, MedGemmaProvider):
        return dict(medgemma_provider.GENERATION_PARAMS)
    return {}
