from __future__ import annotations
from typing import Any

from idicoc_notary.utils import BaseLLMProvider
import os


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None = None, embedding_model: str | None = None):
        # Prefer explicit api_key, otherwise read from environment variable
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.embedding_model = embedding_model or "text-embedding-3-small"
        self.embedding_provider = None
        try:
            import openai

            if api_key:
                openai.api_key = api_key
            elif self.api_key:
                openai.api_key = self.api_key
            self._openai = openai
        except Exception:
            self._openai = None

    def generate(self, prompt: str) -> str:
        if not self._openai:
            raise ImportError("openai package not available")
        resp = self._openai.ChatCompletion.create(
            model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content

    def get_embedding(self, text: str) -> list[float]:
        if not self._openai:
            raise ImportError("openai package not available")
        resp = self._openai.Embeddings.create(input=text, model=self.embedding_model)
        return resp.data[0].embedding


__all__ = ["OpenAIProvider"]
