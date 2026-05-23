from __future__ import annotations
from typing import Any

from idicoc_core.core.graph.property_graph import PropertyGraph


class DeviationQuantifier:
    """Cálculo del Coeficiente de Discrepancia (Sección 5.4) y proyección hacia el manifold."""

    def __init__(self, weights: tuple[float, float, float] = (0.5, 0.3, 0.2)):
        """
        Inicializa con pesos para las componentes de disonancia.
        lambda_inv: peso de d_inv (distancia invariante)
        lambda_logic: peso de d_logic (violaciones lógicas)
        lambda_temporal: peso de d_temporal (violaciones temporales)
        """
        self.lambda_inv, self.lambda_logic, self.lambda_temporal = weights

    def compute_dissonance(
        self,
        candidate: Any,
        canonical_state: Any,
        property_graph: PropertyGraph,
    ) -> float:
        """
        Calcula D_s = λ₁·d_inv + λ₂·d_logic + λ₃·d_temporal.
        
        d_inv: Distancia invariante normalizada [0,1]
        d_logic: Violaciones lógicas (número de conflictos activos, normalizado)
        d_temporal: Violaciones temporales (0 por ahora)
        """
        # d_inv: comparación de igualdad estructural
        d_inv = 0.0 if candidate == (canonical_state.data if hasattr(canonical_state, 'data') else canonical_state) else 1.0
        
        # d_logic: normalizar por número de axiomas activos para evitar que crezca sin límite
        conflicts = property_graph.get_conflicts()
        active_axioms = property_graph.get_active_axioms()
        num_axioms = max(1, len(active_axioms))
        d_logic = min(1.0, float(len(conflicts)) / num_axioms)
        
        # d_temporal: siempre 0 (para implementaciones futuras)
        d_temporal = 0.0
        
        # Suma ponderada
        dissonance = (
            self.lambda_inv * d_inv
            + self.lambda_logic * d_logic
            + self.lambda_temporal * d_temporal
        )
        
        return min(1.0, dissonance)  # Normalizar a [0,1]

    def project_to_manifold(
        self,
        candidate: Any,
        manifold: Any,
        canonical_state: Any,
        property_graph: PropertyGraph,
    ) -> Any:
        """
        Proyecta el candidato hacia el manifold admisible si D_s > epsilon.
        Implementación simple: si está fuera, devuelve el estado canónico.
        """
        dissonance = self.compute_dissonance(candidate, canonical_state, property_graph)
        
        if dissonance <= manifold.epsilon:
            return candidate
        
        # Proyección mínima: devolver el estado canónico (punto más cercano garantizado)
        return canonical_state.data if hasattr(canonical_state, 'data') else canonical_state
