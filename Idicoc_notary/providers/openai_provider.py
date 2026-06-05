from __future__ import annotations
from typing import Any

from idicoc_notary_core.audit.llm_interface import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: str | None = None, embedding_model: str | None = None):
        self.api_key = api_key
        self.embedding_model = embedding_model or "text-embedding-3-small"
        self.embedding_provider = None
        try:
            import openai

            if api_key:
                openai.api_key = api_key
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
