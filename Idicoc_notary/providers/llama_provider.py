from __future__ import annotations
from typing import Any

from idicoc_notary_core.audit.llm_interface import BaseLLMProvider


class LlamaProvider(BaseLLMProvider):
    """Provider wrapper for Llama-style local models.

    This module keeps heavy imports local; if the required libraries are not
    installed the provider will raise ImportError when called.
    """

    def __init__(self, model_path: str | None = None, embedding_model_name: str | None = None):
        self.model_path = model_path
        self.embedding_model_name = embedding_model_name
        # Expose an `embedding_provider` attribute consumable by AuditConfig
        self.embedding_provider = None

        try:
            # Lazy import to avoid hard dependency
            from sentence_transformers import SentenceTransformer

            if embedding_model_name:
                self.embedding_provider = SentenceTransformer(embedding_model_name)
        except Exception:
            self.embedding_provider = None

        # Model instance (lazy)
        self._model = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        try:
            # Try llama-cpp-python first
            from llama_cpp import Llama

            if self.model_path:
                self._model = Llama(model_path=self.model_path)
            else:
                raise RuntimeError("No model_path provided for LlamaProvider")
        except Exception as e:
            raise ImportError(f"Unable to initialize Llama model: {e}")

    def generate(self, prompt: str) -> str:
        self._ensure_model()
        # Basic generate using llama-cpp-python streaming API
        try:
            resp = self._model.generate(prompt)
            # llama-cpp may provide different shapes; coerce to string
            if isinstance(resp, dict) and "choices" in resp:
                return resp["choices"][0]["text"]
            return str(resp)
        except Exception as e:
            raise RuntimeError(f"LlamaProvider.generate failed: {e}")

    def get_embedding(self, text: str) -> list[float]:
        if self.embedding_provider is None:
            raise ImportError("No embedding model available in LlamaProvider")
        vec = self.embedding_provider.encode(text)
        return vec.tolist() if hasattr(vec, "tolist") else list(vec)


__all__ = ["LlamaProvider"]
