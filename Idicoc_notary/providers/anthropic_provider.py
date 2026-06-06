from __future__ import annotations
from typing import Any

from idicoc_notary.utils import BaseLLMProvider
import os


class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None = None, embedding_model: str | None = None):
        # Prefer explicit api_key, otherwise read from environment variable
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.embedding_model = embedding_model
        self.embedding_provider = None
        try:
            import anthropic

            self._anthropic = anthropic
            if api_key:
                self._client = anthropic.Client(api_key)
            elif self.api_key:
                self._client = anthropic.Client(self.api_key)
            else:
                self._client = None
        except Exception:
            self._anthropic = None
            self._client = None

    def generate(self, prompt: str) -> str:
        if not self._client:
            raise ImportError("anthropic package not available or client not configured")
        resp = self._client.completions.create(model="claude-2.1", prompt=prompt)
        return resp.completion

    def get_embedding(self, text: str) -> list[float]:
        # Anthropic embeddings API may differ; raise if unavailable
        raise NotImplementedError("Anthropic embedding adapter not implemented yet")


__all__ = ["AnthropicProvider"]
