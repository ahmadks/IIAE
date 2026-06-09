from __future__ import annotations
import os
from .local_provider import LocalModelProvider


class PhiProvider(LocalModelProvider):
    """Backward-compatible provider wrapper for Phi-style local models."""

    def __init__(self, model_path: str | None = None, embedding_model_name: str | None = None):
        default_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "models_cache", "Phi-3.5-mini-instruct")
        )

        if model_path is None:
            model_path = default_path
        elif (
            not os.path.exists(model_path)
            and os.path.basename(model_path) == "Phi-3.5-mini-instruct"
        ):
            if os.path.exists(default_path):
                model_path = default_path

        super().__init__(
            model_path=model_path,
            embedding_model_name=embedding_model_name,
            temperature=0.0,
            do_sample=False,
            max_new_tokens=80,
        )


__all__ = ["PhiProvider"]
