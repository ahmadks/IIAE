from __future__ import annotations
from dataclasses import dataclass
from typing import Any

from idicoc_core.core.graph.property_graph import PropertyGraph


@dataclass
class Manifold:
    canonical_state_hash: str
    epsilon: float
    active_axioms: list[dict[str, Any]]
    metadata: dict[str, Any]


class ManifoldConstructor:
    """Construye un manifold admisible a partir del estado canónico y el grafo de propiedades."""

    def build(self, canonical_state: Any, property_graph: PropertyGraph, epsilon: float) -> Manifold:
        metadata = {
            "axiom_density": property_graph.compute_axiom_density(),
            "generated_at": canonical_state.metadata.get("timestamp", ""),
        }
        canonical_state_hash = str(hash(repr(canonical_state.data) + canonical_state.metadata.get("timestamp", "")))
        return Manifold(
            canonical_state_hash=canonical_state_hash,
            epsilon=epsilon,
            active_axioms=property_graph.get_active_axioms(),
            metadata=metadata,
        )

    def compute_epsilon(self, mode: str, axiom_density: float, state_stability: float) -> float:
        if mode == "creative":
            base = 0.7
        elif mode == "hybrid":
            base = 0.35
        else:
            base = 0.0

        stability_penalty = max(0.0, min(0.3, 1.0 - state_stability))
        return min(1.0, base + stability_penalty * 0.2)

    def is_within_manifold(self, dissonance_score: float, manifold: Manifold) -> bool:
        return dissonance_score <= manifold.epsilon
