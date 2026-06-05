from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable


class BaseLLMProvider(ABC):
    """Abstract contract for LLM providers and embedding adapters.

    Implementations must keep heavy third-party imports (transformers, openai,
    anthropic, llama-cpp) inside the provider implementation to avoid
    leaking dependencies into the `idicoc_notary_core` package.
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Generate a raw string response from the model."""

    @abstractmethod
    def get_embedding(self, text: str) -> list[float]:
        """Return a vector embedding for `text` as a list of floats."""


__all__ = ["BaseLLMProvider"]
