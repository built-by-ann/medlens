from abc import ABC, abstractmethod


class AIProviderError(Exception):
    """Raised when a provider cannot produce a usable response.

    Covers missing configuration, request failures, timeouts, invalid or
    empty responses, and any other unexpected provider exception. Callers
    only need to handle this one exception type regardless of which
    provider is active.
    """


class AIProvider(ABC):
    """Common interface every AI provider implementation must satisfy.

    Business logic depends only on this interface, never on a specific
    provider, so additional providers can be added without changing
    anything outside the providers package.
    """

    name: str
    model: str

    @abstractmethod
    def generate_summary(self, prompt: str) -> str:
        """Send a prompt to the provider and return the raw text response.

        Raises:
            AIProviderError: if the provider fails to produce a usable
                response for any reason.
        """
        raise NotImplementedError
