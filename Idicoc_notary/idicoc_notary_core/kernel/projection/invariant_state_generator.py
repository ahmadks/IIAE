# idicoc_notary_core/kernel/projection/invariant_state_generator.py
from __future__ import annotations
from typing import Any, Dict
import numpy as np
import warnings

# Deprecation Warning
warnings.warn(
    "The projection/invariant_state_generator module is deprecated under the Standard-Zero architecture.",
    DeprecationWarning,
    stacklevel=2,
)


class CanonicalState:
    """
    Representación formal del estado canónico V_hat generado por el ISG.
    [DEPRECATED STUB]
    """

    def __init__(self, measure_vector: Any, metadata: Dict):
        self.measure_vector = measure_vector
        self.metadata = metadata
        self.is_canonical = True

    def get_representation(self, preference: str = "measure") -> Any:
        return self.measure_vector

    @property
    def semantic_vector(self) -> Any:
        return self.measure_vector

    def __str__(self) -> str:
        return str(self.measure_vector)

    def __repr__(self) -> str:
        return f"CanonicalState(measure_vector={self.measure_vector!r}, metadata={self.metadata!r})"


class InvariantStateGenerator:
    """
    MAII-ISG — Canonical Invariant State Generator.
    [DEPRECATED STUB]
    """

    def __init__(
        self,
        anchor: Any = None,
        registry: Any = None,
        require_embedding_model: bool = False,
        config: Any = None,
    ):
        self._anchor = anchor
        self._registry = registry
        self.require_embedding_model = require_embedding_model
        self.config = config

    def generate(self, admitted_input: Any) -> CanonicalState:
        vector = admitted_input
        if isinstance(admitted_input, np.ndarray):
            vector = admitted_input
        elif hasattr(admitted_input, "distribution"):
            vector = admitted_input.distribution
        elif hasattr(admitted_input, "data"):
            vector = admitted_input.data

        if isinstance(vector, str):
            try:
                from idicoc_notary_core.utils.embedding_service import EmbeddingService
                vector = EmbeddingService().encode(vector)
            except Exception:
                vector = np.zeros(32, dtype=float)

        metadata = {
            "stage": "MAII‑ISG (Deprecated Stub)",
            "timestamp": "2026-06-05T12:00:00Z",
            "projection_history": [],
            "embedding_fallback_incidents": 0,
        }
        return CanonicalState(measure_vector=vector, metadata=metadata)
