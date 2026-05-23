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

    No usa métricas, no usa distancias, no usa tolerancias.
    La ontología monaxiomática exige igualdad estructural estricta.
    """

    def __init__(self, anchor: SourceAnchor):
        self._anchor = anchor  # La constante universal k

    def verify_alignment(self, canonical_state: CanonicalState, tolerance: float | None = None) -> None:
        """
        Ejecuta la prueba de bisimulación:
            V^t ≡ k

        Si la igualdad estructural falla y no está dentro del umbral aceptable → AlignmentBreach.
        """
        if tolerance is None or tolerance == 0.0:
            requires_alignment = True
        else:
            requires_alignment = False

        if requires_alignment and not self._is_bisimilar(canonical_state.data, self._anchor.identity):
            raise AlignmentBreach(
                message="Fallo de bisimulación: V^t no coincide con k.",
                invalid_state=canonical_state.data,
                context={
                    "expected_k": repr(self._anchor.identity),
                    "received_Vt": repr(canonical_state.data)
                },
                origin="InvariantVerifier.verify_alignment"
            )

    def _is_bisimilar(self, state_data: Any, k_identity: Any) -> bool:
        """
        En la ontología monaxiomática:
            Bisimulación ≡ Igualdad estructural estricta.

        No hay métricas, no hay distancias, no hay epsilon.
        """
        return state_data == k_identity
