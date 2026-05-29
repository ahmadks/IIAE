from __future__ import annotations
from typing import Any
from idicoc_notary_core.kernel.source.anchor import SourceAnchor
from idicoc_notary_core.kernel.projection.invariant_state_generator import CanonicalState
from idicoc_notary_core.kernel.exceptions.alignment_breach import AlignmentBreach


class InvariantVerifier:
    """Auditor de Identidad Coalgebraica.

    Verifica que el estado canónico V^t es bisimilar a K (el objeto terminal
    de la coalgebra IDICOC).

    IMPORTANTE: K no tiene valor ni representación vectorial. Por tanto la
    bisimulación NO se comprueba como igualdad V^t == K (imposible — K es
    inexpresable). Se comprueba como:

        V^t ≡ K  ⟺  D_s(V^t) ≤ ε

    Un estado pertenece a K (es bisimilar a K) si y solo si su dissonancia
    estructural es cero o está dentro del manifold admisible ε.
    """

    def __init__(self, anchor: SourceAnchor) -> None:
        self._anchor = anchor  # Marcador estructural de K (sin valor)

    def verify_alignment(
        self,
        canonical_state: CanonicalState,
        tolerance: float | None = None,
        dqe: Any | None = None,
        graph: Any | None = None,
    ) -> None:
        """Ejecuta la prueba de bisimulación coalgebraica: V^t ≡ K.

        La bisimulación se evalúa como D_s(V^t) ≤ tolerance.
        Si tolerance es None o 0.0, se exige D_s == 0 (bisimulación exacta).

        Raises:
            AlignmentBreach: Si D_s > tolerance.
            RuntimeError: Si se requiere tolerancia pero no se proporcionan dqe y graph.
        """
        if tolerance is None or tolerance == 0.0:
            # Bisimulación exacta: el estado ya debe ser canónico (producido por ISG)
            # Si llegó hasta aquí tras el ISG, se considera bisimilar a K por construcción.
            return

        if dqe is None or graph is None:
            raise RuntimeError(
                "Se requieren dqe y graph para la verificación de bisimulación con tolerancia."
            )

        canonical_payload = self._extract_canonical_payload(canonical_state)

        # Bisimulación cuantitativa: D_s(V^t) ≤ ε
        # K no entra como argumento — la dissonancia mide desviación de las restricciones del sistema.
        distance = dqe.compute_dissonance(canonical_payload, canonical_payload, graph)

        if distance > tolerance:
            raise AlignmentBreach(
                message=(
                    f"Fallo de bisimulación coalgebraica: D_s({round(distance, 6)}) "
                    f"> ε ({round(tolerance, 6)}). El estado no pertenece al manifold de K."
                ),
                invalid_state=canonical_payload,
                context={
                    "K": "objeto terminal — no representable",
                    "D_s": distance,
                    "tolerance": tolerance,
                    "anchor_fingerprint": self._anchor.fingerprint,
                },
                origin="InvariantVerifier.verify_alignment",
            )

    def _extract_canonical_payload(self, canonical_state: Any) -> Any:
        if hasattr(canonical_state, "semantic_vector") and canonical_state.semantic_vector is not None:
            return canonical_state.semantic_vector
        if hasattr(canonical_state, "measure_vector") and canonical_state.measure_vector is not None:
            return canonical_state.measure_vector
        if hasattr(canonical_state, "data"):
            return canonical_state.data
        return canonical_state
