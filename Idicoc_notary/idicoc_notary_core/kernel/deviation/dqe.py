from __future__ import annotations
from typing import Any
import math

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

    def embed(self, value: Any) -> list[float]:
        if isinstance(value, str):
            return [float(len(value))]
        if hasattr(value, "data"):
            return self.embed(value.data)
        if isinstance(value, (list, tuple, set)):
            return [float(len(value))]
        return [0.0]

    def _vector_norm(self, vector: list[float]) -> float:
        return math.sqrt(sum(x * x for x in vector))

    def _subtract_vectors(self, a: list[float], b: list[float]) -> list[float]:
        length = max(len(a), len(b))
        return [(a[i] if i < len(a) else 0.0) - (b[i] if i < len(b) else 0.0) for i in range(length)]

    def _violation_penalty(self, y: Any, axiom: dict[str, Any]) -> float:
        if not isinstance(axiom, dict):
            return 0.0
        axiom_text = " ".join(str(v) for v in axiom.values())
        if isinstance(y, str) and axiom_text and axiom_text in y:
            return 0.0
        return 1.0

    def _gradient(self, y: Any, V_hat: Any, G: Any) -> list[float]:
        if isinstance(y, str):
            return [0.0]
        diff = self._subtract_vectors(self.embed(y), self.embed(getattr(V_hat, "data", V_hat)))
        norm = self._vector_norm(diff)
        if norm < 1e-9:
            return [0.0 for _ in diff]
        return [component / norm for component in diff]

    def compute_dissonance(self, y: Any, V_hat: Any, G: Any) -> float:
        diff = self._subtract_vectors(self.embed(y), self.embed(getattr(V_hat, "data", V_hat)))
        d_inv = self._vector_norm(diff) / MAX_DIST
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
            if isinstance(candidate, list):
                candidate = [candidate[i] - lr * grad[i] for i in range(len(candidate))]
            else:
                break
        return candidate
