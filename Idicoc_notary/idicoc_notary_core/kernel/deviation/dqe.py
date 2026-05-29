from __future__ import annotations
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from idicoc_notary_core.audit.dse.dissonance_strategy import DissonanceStrategy


class DissonanceCalculator:
    """Cuantificador de disonancia coalgebraico. Delega en DissonanceStrategy."""

    def __init__(
        self,
        strategy: "DissonanceStrategy | None" = None,
        lambda_0: float = 0.0,
        lambda_1: float = 0.5,
        lambda_2: float = 0.4,
        lambda_3: float = 0.1,
        lambda_4: float = 0.0,
        lambda_5: float = 0.0,
        lambda_6: float = 0.0,
    ) -> None:
        self.strategy = strategy
        self.lambda_0 = lambda_0
        self.lambda_1 = lambda_1
        self.lambda_2 = lambda_2
        self.lambda_3 = lambda_3
        self.lambda_4 = lambda_4
        self.lambda_5 = lambda_5
        self.lambda_6 = lambda_6

    def set_strategy(self, strategy: "DissonanceStrategy") -> None:
        self.strategy = strategy

    def compute_dissonance(
        self, y: Any, V_hat: Any, G_t: Any, context_input: list | None = None
    ) -> float:
        if self.strategy is not None:
            if hasattr(self.strategy, "compute_dissonance"):
                return self.strategy.compute_dissonance(y, V_hat, G_t, context_input=context_input)
            # Si la estrategia no tiene compute_dissonance (e.g. SemanticDissonanceStrategy)
            # llamamos a su compute clásico y extraemos D_s
            policies = G_t.get_active_policies() if hasattr(G_t, "get_active_policies") else []
            try:
                D_s, _, _, _, _ = self.strategy.compute(
                    audit_input=y,
                    context_input=[],
                    context_policies=[str(a) for a in policies],
                    epsilon=0.0,
                )
                return float(D_s)
            except Exception:
                pass

        return self._fallback_dissonance(y, V_hat, G_t)

    def project_to_manifold(
        self,
        y: Any,
        manifold: Any,
        V_hat: Any,
        G_t: Any,
        max_iter: int = 10,
        context_input: list | None = None,
    ) -> Any:
        epsilon = getattr(manifold, "epsilon", 0.0)
        if self.strategy is not None:
            if hasattr(self.strategy, "project"):
                return self.strategy.project(
                    y, epsilon, V_hat, G_t, max_iter, context_input=context_input
                )
            # Fallback para SemanticDissonanceStrategy
            try:
                policies = G_t.get_active_policies() if hasattr(G_t, "get_active_policies") else []
                _, _, corrected, _, _ = self.strategy.compute(
                    audit_input=y,
                    context_input=[],
                    context_policies=[str(a) for a in policies],
                    epsilon=epsilon,
                )
                return corrected
            except Exception:
                pass

        return self._fallback_project(y, epsilon, V_hat, G_t, max_iter)

    # ── Fallbacks básicos (sin strategy disponible) ───────────────────────────

    def _fallback_dissonance(self, y: Any, V_hat: Any, G_t: Any) -> float:
        import math

        len_y = len(str(y)) if y is not None else 0
        len_v = len(str(V_hat)) if V_hat is not None else 0
        d_inv = abs(len_y - len_v) / max(len_y, len_v, 1)

        policies = G_t.get_active_policies() if hasattr(G_t, "get_active_policies") else []
        if policies:
            d_logic = G_t.evaluate(y) if hasattr(G_t, "evaluate") else 0.0
        else:
            d_logic = 0.0

        d_temporal = (
            G_t.compute_temporal(y)
            if hasattr(G_t, "compute_temporal")
            else G_t.compute_d_temporal(y) if hasattr(G_t, "compute_d_temporal") else 0.0
        )

        return max(
            0.0,
            min(
                1.0,
                self.lambda_0 * 0.0
                + self.lambda_1 * d_inv
                + self.lambda_2 * d_logic
                + self.lambda_3 * d_temporal
                + self.lambda_4 * 0.0
                + self.lambda_5 * 0.0
                + self.lambda_6 * 0.0,
            ),
        )

    def _fallback_project(self, y: Any, epsilon: float, V_hat: Any, G_t: Any, max_iter: int) -> Any:
        if self._fallback_dissonance(y, V_hat, G_t) <= epsilon:
            return y
        if isinstance(y, str):
            return V_hat if isinstance(V_hat, str) else str(V_hat)
        return V_hat
