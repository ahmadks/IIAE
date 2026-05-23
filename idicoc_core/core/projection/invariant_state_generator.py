# idicoc_core/core/projection/invariant_generator.py
from __future__ import annotations
from typing import Any, Dict
from datetime import datetime

from idicoc_core.exceptions.integrity_breach import InvariantStateBreach
from idicoc_core.core.source.anchor import SourceAnchor
from idicoc_core.core.verification.registry import ProjectionRegistry


class CanonicalState:
    """
    Representación formal del estado invariante V^t.
    Es el único tipo de estado que puede entrar al Verifier y al CTM.
    """
    def __init__(self, data: Any, metadata: Dict):
        self.data = data
        self.metadata = metadata
        self.is_canonical = True


class InvariantStateGenerator:
    """
    MAII‑ISG — Canonical Invariant State Generator (ontología monaxiomática).

    Rol:
    - Recibe entrada ya admitida por el AEM (cualquier tipo de señal).
    - Aplica una contracción determinista hacia un estado invariante V^t.
    - No verifica identidad (eso es del InvariantVerifier).
    - Si no puede proyectar, lanza InvariantStateBreach.
    """

    def __init__(self, anchor: SourceAnchor, registry: ProjectionRegistry):
        self._anchor = anchor          # k (coálgebra terminal)
        self._registry = registry      # registro de proyecciones previas (no axiomas)

    def generate(self, admitted_input: Any) -> CanonicalState:
        """
        Proyecta la señal admitida a un estado canónico V^t.
        """
        try:
            projected = self._project_to_invariant(admitted_input)
        except Exception as e:
            # Cualquier fallo aquí es una violación de integridad de proyección
            raise InvariantStateBreach(
                message="Fallo en la proyección canónica (MAII‑ISG).",
                invalid_state=admitted_input,
                context={"error": str(e)},
                origin="MAII‑ISG.generate"
            )

        metadata = {
            "stage": "MAII‑ISG",
            "timestamp": datetime.utcnow().isoformat(),
            "projection_history": self._registry.get_projection_trace(),
        }

        return CanonicalState(projected, metadata)

    def _project_to_invariant(self, data: Any) -> Any:
        """
        Operador de contracción hacia la estructura invariante.

        En la ontología monaxiomática:
            f_ISG(data) → V^t

        No asume tipo de señal: texto, embedding, señal analógica, estado de firmware, etc.
        La implementación concreta puede especializarse por sustrato, pero la interfaz es única.
        """
        # Aquí iría la lógica matemática real (Annex J).
        # Versión mínima: identidad (asumiendo que el AEM ya filtró lo inadmisible).
        return data
