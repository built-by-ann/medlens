"""Provider registry for the evaluation runner (Issue #89).

Maps a CLI-facing provider name to a way to construct the real, production
AIProvider class, reading the same environment variables
build_ai_summary_service() (app/ai/service.py) already reads via Settings,
just constructed directly rather than through Settings/
build_ai_summary_service()/get_ai_summary_service(). The evaluation runner
needs several providers active in one process, which AI_PROVIDER's
single-active-provider design isn't suited for; constructing Settings at
all would also require DATABASE_URL/JWT_SECRET_KEY, which have nothing to
do with evaluation; see benchmark/README.md for the full reasoning.

Gemini takes a credential (api_key); openbiollm/medgemma take no
credential at all - both are served locally by Ollama, addressed by
model + base_url instead (Issue #91's local-inference migration). Since
the three providers no longer share one constructor shape, each entry is
a small zero-argument builder function rather than a generic
(class, env_var) tuple.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable

from app.ai.providers import medgemma_provider, openbiollm_provider
from app.ai.providers.base import AIProvider
from app.ai.providers.gemini_provider import GeminiProvider
from app.ai.providers.medgemma_provider import MedGemmaProvider
from app.ai.providers.openbiollm_provider import OpenBioLLMProvider


def _build_gemini() -> AIProvider:
    return GeminiProvider(api_key=os.environ.get("GEMINI_API_KEY"))


def _build_openbiollm() -> AIProvider:
    return OpenBioLLMProvider(
        model=os.environ.get("OPENBIOLLM_MODEL", openbiollm_provider.DEFAULT_MODEL),
        base_url=os.environ.get("OLLAMA_BASE_URL", openbiollm_provider.DEFAULT_BASE_URL),
    )


def _build_medgemma() -> AIProvider:
    return MedGemmaProvider(
        model=os.environ.get("MEDGEMMA_MODEL", medgemma_provider.DEFAULT_MODEL),
        base_url=os.environ.get("OLLAMA_BASE_URL", medgemma_provider.DEFAULT_BASE_URL),
    )


# name -> zero-argument builder. Order here is the default --providers
# order (see cli.py).
PROVIDER_REGISTRY: dict[str, Callable[[], AIProvider]] = {
    "gemini": _build_gemini,
    "openbiollm": _build_openbiollm,
    "medgemma": _build_medgemma,
}

PROVIDER_NAMES: tuple[str, ...] = tuple(PROVIDER_REGISTRY.keys())


def build_provider(name: str) -> AIProvider:
    """Constructs the named provider directly, reading its configuration
    from the process environment (already best-effort loaded from
    backend/.env by cli.py's _load_env()); no Settings instance, no
    database/JWT configuration required.
    """
    try:
        builder = PROVIDER_REGISTRY[name]
    except KeyError:
        raise ValueError(
            f"Unknown provider: {name!r}. Known providers: {', '.join(PROVIDER_NAMES)}"
        ) from None

    return builder()


def inference_backend_for(provider: AIProvider) -> str | None:
    """The inference backend a given AIProvider instance is actually
    served through, if any; None for GeminiProvider (no such concept
    applies to it). Read from each provider module's own
    INFERENCE_BACKEND constant rather than hardcoded here, so this always
    reflects reality even if a provider's serving mechanism changes
    again in the future.
    """
    if isinstance(provider, OpenBioLLMProvider):
        return openbiollm_provider.INFERENCE_BACKEND
    if isinstance(provider, MedGemmaProvider):
        return medgemma_provider.INFERENCE_BACKEND
    return None


def generation_params_for(provider: AIProvider) -> dict:
    """The hardcoded GENERATION_PARAMS constant for a provider that has
    one, copied (never the module's own dict, so a caller mutating the
    result can't affect the real constant); {} for GeminiProvider, which
    has no equivalent parameter dict (its only generation configuration,
    JSON_RESPONSE_CONFIG, isn't in this shape).
    """
    if isinstance(provider, OpenBioLLMProvider):
        return dict(openbiollm_provider.GENERATION_PARAMS)
    if isinstance(provider, MedGemmaProvider):
        return dict(medgemma_provider.GENERATION_PARAMS)
    return {}


def runtime_version_for(provider: AIProvider) -> str | None:
    """The installed Ollama server's own version string, for providers
    backed by it; None for GeminiProvider, and None (rather than raising)
    if the Ollama server can't be reached, since this is a best-effort
    reproducibility detail, not a precondition for running the benchmark
    - a genuinely unreachable Ollama server will already surface loudly,
    per-case, as a connection_error from the provider itself once cases
    actually run.

    Deliberately not part of generation_params_for's dict: the Ollama
    runtime is a connection/environment detail, not a generation
    parameter, matching the same distinction Settings.ollama_base_url
    draws from GENERATION_PARAMS in the provider modules themselves.
    """
    if not isinstance(provider, (OpenBioLLMProvider, MedGemmaProvider)):
        return None

    try:
        with urllib.request.urlopen(f"{provider.base_url}/api/version", timeout=5) as response:
            return json.loads(response.read()).get("version")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None
