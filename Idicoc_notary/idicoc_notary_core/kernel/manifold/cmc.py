from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from idicoc_notary_core.utils.hashing import canonical_json, sha256_hex


class Manifold:
    def __init__(
        self,
        canonical_state_hash: str,
        epsilon: float,
        active_policies: list[dict[str, Any]],
        canonical_state: Any,
        graph: Any,
        dqe: Any = None,
    ) -> None:
        self.canonical_state_hash = canonical_state_hash
        self._epsilon = epsilon
        self.active_policies = active_policies
        self.canonical_state = canonical_state
        self.graph = graph
        self.dqe = dqe

    @property
    def epsilon(self) -> float:
        return self._epsilon

    def contains(self, point: Any) -> bool:
        candidate = point
        if hasattr(point, "data"):
            candidate = point.data
        elif hasattr(point, "semantic_vector") or hasattr(point, "measure_vector"):
            candidate = getattr(point, "semantic_vector", None)
            if candidate is None:
                candidate = getattr(point, "measure_vector", point)

        if self.dqe is not None:
            dissonance = self.dqe.compute_dissonance(candidate, self.canonical_state, self.graph)
            return dissonance <= self.epsilon

        return True


class ManifoldConstructor:
    """Constructor de manifold con constantes estáticas."""

    def __init__(self, dqe: Any | None = None):
        self.dqe = dqe

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
