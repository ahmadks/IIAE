# idicoc_core/core/verification/verifier.py
from __future__ import annotations
from typing import Any
from idicoc_core.core.source.anchor import SourceAnchor
from idicoc_core.core.projection.invariant_state_generator import CanonicalState
from idicoc_core.exceptions.alignment_breach import AlignmentBreach


class InvariantVerifier:
    """
    InvariantVerifier — Auditor de Identidad Ontológica.

    Su única responsabilidad:
        Verificar que el estado canónico V^t es bisimilar a la
        coálgebra terminal k (SourceAnchor.identity).

    En modo tolerante, utiliza una métrica de disonancia para comprobar
    si la desviación estructural está dentro de epsilon.
    """

    def __init__(self, anchor: SourceAnchor):
        self._anchor = anchor  # La constante universal k

    def verify_alignment(
        self,
        canonical_state: CanonicalState,
        tolerance: float | None = None,
        dqe: Any | None = None,
        graph: Any | None = None,
    ) -> None:
        """
        Ejecuta la prueba de bisimulación:
            V^t ≡ k

        Si la igualdad estructural falla y no está dentro del umbral aceptable → AlignmentBreach.
        """
        if tolerance is None or tolerance == 0.0:
            if not self._is_bisimilar(canonical_state.data, self._anchor.identity):
                raise AlignmentBreach(
                    message="Fallo de bisimulación: V^t no coincide con k.",
                    invalid_state=canonical_state.data,
                    context={
                        "expected_k": repr(self._anchor.identity),
                        "received_Vt": repr(canonical_state.data),
                    },
                    origin="InvariantVerifier.verify_alignment",
                )
            return

        if dqe is None or graph is None:
            raise RuntimeError("Se requiere DQE y grafo para verificación con tolerancia.")

        distance = dqe.compute_dissonance(canonical_state.data, self._anchor.identity, graph)
        if distance > tolerance:
            raise AlignmentBreach(
                message="Fallo de alineación tolerante: la disonancia excede epsilon.",
                invalid_state=canonical_state.data,
                context={
                    "expected_k": repr(self._anchor.identity),
                    "received_Vt": repr(canonical_state.data),
                    "distance": distance,
                    "tolerance": tolerance,
                },
                origin="InvariantVerifier.verify_alignment",
            )

    def _is_bisimilar(self, state_data: Any, k_identity: Any) -> bool:
        return state_data == k_identity
