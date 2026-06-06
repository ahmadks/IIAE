from __future__ import annotations
from .local_provider import LocalModelProvider


class PhiProvider(LocalModelProvider):
    """Backward-compatible provider wrapper for Phi-style local models."""

    def __init__(self, model_path: str | None = None, embedding_model_name: str | None = None):
        model_path = model_path or "models_cache/Phi-3.5-mini-instruct"
        super().__init__(
            model_path=model_path,
            embedding_model_name=embedding_model_name,
            temperature=0.0,
            do_sample=False,
            max_new_tokens=80,
        )


__all__ = ["PhiProvider"]
