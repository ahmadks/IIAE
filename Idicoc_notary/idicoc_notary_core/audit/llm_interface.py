from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class BaseLLMProvider(Protocol):
    """Abstract protocol for LLM providers and embedding adapters.

    Implementations must keep heavy third-party imports (transformers, openai,
    anthropic, llama-cpp) inside the provider implementation to avoid
    leaking dependencies into the `idicoc_notary_core` package.
    """

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate a raw string response from the model."""

    def get_embedding(self, text: str) -> list[float]:
        """Return a vector embedding for `text` as a list of floats."""



__all__ = ["BaseLLMProvider"]
