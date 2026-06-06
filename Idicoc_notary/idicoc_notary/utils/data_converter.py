from __future__ import annotations
from typing import Any

import numpy as np


class DataConverter:
    """Centraliza conversiones entre formatos (text, vectors, payloads)."""

    @staticmethod
    def to_text(obj: Any) -> str:
        if obj is None:
            return ""
        if isinstance(obj, str):
            return obj
        if hasattr(obj, "text_content"):
            return str(getattr(obj, "text_content"))
        if hasattr(obj, "data"):
            return str(getattr(obj, "data"))
        if hasattr(obj, "semantic_vector"):
            return str(getattr(obj, "semantic_vector"))
        return str(obj)

    @staticmethod
    def normalize_payload(item: Any) -> Any:
        """Normalize payloads recursively into JSON-serializable primitives."""
        if hasattr(item, "source_text") and hasattr(item, "distribution"):
            dist = getattr(item, "distribution", None)
            if hasattr(dist, "tolist"):
                try:
                    dist = dist.tolist()
                except Exception:
                    dist = str(dist)
            return {
                "payload_type": getattr(item, "payload_type", None),
                "source_text": getattr(item, "source_text", None),
                "text_content": getattr(item, "text_content", None),
                "distribution": dist,
            }
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, (list, tuple)):
            return [DataConverter.normalize_payload(v) for v in item]
        return item


__all__ = ["DataConverter"]
