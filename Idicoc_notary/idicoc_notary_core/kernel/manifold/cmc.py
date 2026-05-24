from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from idicoc_notary_core.utils.hashing import canonical_json, sha256_hex


@dataclass
class Manifold:
    canonical_state_hash: str
    epsilon: float
    active_axioms: list[dict[str, Any]]
    canonical_state: Any
    graph: Any

    def contains(self, point: Any) -> bool:
        if hasattr(point, "data"):
            candidate = point.data
        else:
            candidate = point

        if hasattr(self, "dqe") and self.dqe is not None:
            dissonance = self.dqe.compute_dissonance(candidate, self.canonical_state, self.graph)
            return dissonance <= self.epsilon

        return True


class ManifoldConstructor:
    """Constructor de manifold simplificado con actualización dinámica de epsilon."""

    def __init__(self, dqe: Any | None = None):
        self.dqe = dqe

    def compute_epsilon(self, axiom_density: float, stability_factor: float) -> float:
        base = 0.05 + 0.5 * axiom_density * stability_factor
        return min(1.0, max(0.0, base))

    def update_epsilon(
        self,
        current_eps: float,
        axiom_density: float,
        dissonance_variance: float = 0.0,
        alpha: float = 0.1,
    ) -> float:
        target = self.compute_epsilon(axiom_density, 1.0 - dissonance_variance)
        return (1.0 - alpha) * current_eps + alpha * target

    def build(self, canonical_state: Any, graph: Any, epsilon: float) -> Manifold:
        canonical_hash = sha256_hex(canonical_json(getattr(canonical_state, "data", canonical_state)))
        active_axioms = graph.get_active_axioms() if hasattr(graph, "get_active_axioms") else []
        manifold = Manifold(
            canonical_state_hash=canonical_hash,
            epsilon=epsilon,
            active_axioms=active_axioms,
            canonical_state=getattr(canonical_state, "data", canonical_state),
            graph=graph,
        )
        manifold.dqe = self.dqe
        return manifold
