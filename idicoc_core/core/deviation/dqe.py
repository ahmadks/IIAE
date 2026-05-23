from __future__ import annotations
from typing import Any

import numpy as np


MAX_DIST = 1.0


class DeviationQuantifier:
    """Cuantificador de disonancia coalgebraico para el kernel."""

    def __init__(
        self,
        lambda_inv: float = 0.5,
        lambda_logic: float = 0.4,
        lambda_temporal: float = 0.1,
        delta_fp: float = 0.15,
    ):
        self.lambda_inv = lambda_inv
        self.lambda_logic = lambda_logic
        self.lambda_temporal = lambda_temporal
        self.delta_fp = delta_fp

    def embed(self, value: Any) -> np.ndarray:
        if isinstance(value, str):
            return np.array([float(len(value))])
        if hasattr(value, "data"):
            return self.embed(value.data)
        if isinstance(value, (list, tuple)):
            return np.array([float(len(value))])
        return np.array([0.0])

    def _violation_penalty(self, y: Any, axiom: dict[str, Any]) -> float:
        if not isinstance(axiom, dict):
            return 0.0
        axiom_text = " ".join(str(v) for v in axiom.values())
        if isinstance(y, str) and axiom_text and axiom_text in y:
            return 0.0
        return 1.0

    def _gradient(self, y: Any, V_hat: Any, G: Any) -> np.ndarray:
        if isinstance(y, str):
            return np.zeros(1)
        diff = self.embed(y) - self.embed(getattr(V_hat, "data", V_hat))
        norm = np.linalg.norm(diff)
        return diff / (norm + 1e-9)

    def compute_dissonance(self, y: Any, V_hat: Any, G: Any) -> float:
        d_inv = np.linalg.norm(self.embed(y) - self.embed(getattr(V_hat, "data", V_hat))) / MAX_DIST
        logic_penalties = [self._violation_penalty(y, ax) for ax in G.get_active_axioms()] if hasattr(G, "get_active_axioms") else []
        d_logic = sum(logic_penalties)
        d_logic = min(1.0, d_logic / max(1, len(logic_penalties)))
        d_temp = 0.0
        return self.lambda_inv * d_inv + self.lambda_logic * d_logic + self.lambda_temporal * d_temp

    def project_to_manifold(
        self,
        y: Any,
        manifold: Any,
        V_hat: Any,
        G: Any,
        max_iter: int = 10,
        lr: float = 0.1,
    ) -> Any:
        if isinstance(y, str):
            return y

        candidate = y
        for _ in range(max_iter):
            if self.compute_dissonance(candidate, V_hat, G) <= manifold.epsilon:
                break
            grad = self._gradient(candidate, V_hat, G)
            if isinstance(candidate, np.ndarray):
                candidate = candidate - lr * grad
            else:
                break
        return candidate
