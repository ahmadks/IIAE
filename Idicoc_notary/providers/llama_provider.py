from __future__ import annotations
from .local_provider import LocalModelProvider


class LlamaProvider(LocalModelProvider):
    """Backward-compatible provider wrapper for Llama-style local models."""

    def __init__(self, model_path: str | None = None, embedding_model_name: str | None = None):
        super().__init__(
            model_path=model_path,
            embedding_model_name=embedding_model_name,
            temperature=0.7,
            do_sample=True,
            max_new_tokens=150,
        )


__all__ = ["LlamaProvider"]
