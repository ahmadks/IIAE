from __future__ import annotations
from typing import Any, Dict, Optional
import numpy as np
from idicoc_core.exceptions import InvariantStateBreach
from idicoc_core.isg.graph_manager import PropertyGraph
from idicoc_core.dse.evaluator import PropertyGraphEvaluator
from idicoc_core.utils.string_utils import StringUtils

class CanonicalState:
    """Representación formal del estado canónico V_hat generado por el ISG."""

    def __init__(self, measure_vector: Any, metadata: Dict):
        self.measure_vector = measure_vector
        self.metadata = metadata
        self.is_canonical = True

    def get_representation(self, preference: str = "measure") -> Any:
        return self.measure_vector

    @property
    def semantic_vector(self) -> Any:
        return self.measure_vector

    def __repr__(self) -> str:
        return f"CanonicalState(measure_vector={self.measure_vector!r}, metadata={self.metadata!r})"


class InvariantStateGenerator:
    """MAII-ISG — Canonical Invariant State Generator.

    Converts the input prompt to a vector and projects it onto the manifold.
    Raises InvariantStateBreach if a hard policy is violated.
    """

    def __init__(
        self,
        anchor: Any,
        graph_manager: PropertyGraph,
        config: Any = None,
    ):
        self._anchor = anchor
        self.graph_manager = graph_manager
        self.config = config

    def _text_to_vector(self, text: str) -> np.ndarray:
        model_name = getattr(self.config, "semantic_embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
        try:
            return StringUtils.to_vector(text, model_name=model_name)
        except Exception:
            return np.zeros(384, dtype=float)

    def project(self, user_input: str) -> np.ndarray:
        """
        Proyecta el input hacia la variedad de invarianza.
        Si el input no cumple con las restricciones del Grafo (disonancia infinita),
        bloqueamos antes del LLM.
        """
        # 1. Convertir a vector (sin texto)
        input_vector = self._text_to_vector(user_input)
        
        # 2. Proyección sobre el Grafo (sin alterar el prompt original)
        # Si la proyección no es posible (disonancia infinita), bloqueamos antes del LLM.
        evaluator = PropertyGraphEvaluator(self.graph_manager, self.config)
        try:
            d_logic = evaluator.evaluate(user_input)
        except Exception:
            d_logic = 0.0

        if d_logic == float("inf"):
            raise InvariantStateBreach(
                message="Input Invariance Containment Breach: Infinite dissonance detected.",
                invalid_state=user_input,
                origin="InvariantStateGenerator.project"
            )

        projected_vector = self.graph_manager.project_to_manifold(input_vector)
        return projected_vector
