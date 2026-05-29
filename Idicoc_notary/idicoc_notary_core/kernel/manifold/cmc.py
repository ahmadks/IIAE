from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from idicoc_notary_core.utils.hashing import canonical_json, sha256_hex


@dataclass
class Manifold:
    canonical_state_hash: str
    epsilon: float
    active_policies: list[dict[str, Any]]
    canonical_state: Any
    graph: Any
    dqe: Any = None

    def contains(self, point: Any) -> bool:
        candidate = point
        if hasattr(point, "data"):
            candidate = point.data
        elif hasattr(point, "semantic_vector") or hasattr(point, "measure_vector"):
            candidate = getattr(point, "semantic_vector", None)
            if candidate is None:
                candidate = getattr(point, "measure_vector", point)

        if hasattr(self, "dqe") and self.dqe is not None:
            dissonance = self.dqe.compute_dissonance(candidate, self.canonical_state, self.graph)
            return dissonance <= self.epsilon

        return True


class ManifoldConstructor:
    """Constructor de manifold simplificado con actualización dinámica de epsilon."""

    def __init__(self, dqe: Any | None = None):
        self.dqe = dqe

    def compute_epsilon(self, policy_density: float, stability_factor: float) -> float:
        base = 0.05 + 0.5 * policy_density * stability_factor
        return min(1.0, max(0.0, base))

    def update_epsilon(
        self,
        current_eps: float,
        policy_density: float,
        dissonance_variance: float = 0.0,
        alpha: float = 0.1,
    ) -> float:
        target = self.compute_epsilon(policy_density, 1.0 - dissonance_variance)
        return (1.0 - alpha) * current_eps + alpha * target

    def build(self, canonical_state: Any, graph: Any, epsilon: float) -> Manifold:
        representative = canonical_state
        if hasattr(canonical_state, "semantic_vector") or hasattr(canonical_state, "measure_vector"):
            representative = getattr(canonical_state, "semantic_vector", None)
            if representative is None:
                representative = getattr(canonical_state, "measure_vector", canonical_state)

        canonical_hash = sha256_hex(canonical_json(representative))
        active_policies = graph.get_active_policies() if hasattr(graph, "get_active_policies") else []
        manifold = Manifold(
            canonical_state_hash=canonical_hash,
            epsilon=epsilon,
            active_policies=active_policies,
            canonical_state=representative,
            graph=graph,
        )
        manifold.dqe = self.dqe
        return manifold
