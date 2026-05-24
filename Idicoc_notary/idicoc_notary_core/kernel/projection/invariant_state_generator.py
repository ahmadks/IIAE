# idicoc_notary_core/kernel/projection/invariant_generator.py
from __future__ import annotations
from typing import Any, Dict
from datetime import datetime, timezone

from idicoc_notary_core.kernel.exceptions.integrity_breach import InvariantStateBreach
from idicoc_notary_core.kernel.source.anchor import SourceAnchor
from idicoc_notary_core.kernel.verification.registry import ProjectionRegistry


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

    def __init__(self, anchor: SourceAnchor, registry: ProjectionRegistry, delta_fp: float = 0.15):
        self._anchor = anchor          # k (coálgebra terminal)
        self._registry = registry      # registro de proyecciones previas (no axiomas)
        self.delta_fp = delta_fp

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
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "projection_history": self._registry.get_projection_trace(),
        }

        return CanonicalState(projected, metadata)

    def _project_to_invariant(self, data: Any) -> Any:
        """
        Operador de contracción hacia la estructura invariante.

        En la ontología monaxiomática:
            f_ISG(data) → V^t

        Se aplica una normalización básica y un colapso por tolerancia δ_fp.
        """
        if hasattr(data, "data"):
            return self._project_to_invariant(data.data)

        if isinstance(data, str):
            normalized = self._normalize_text(data)
            if self._approx_distance(normalized, str(self._anchor.identity)) < self.delta_fp:
                return self._anchor.identity
            return self._canonical_text(normalized)

        if isinstance(data, dict) or isinstance(data, list):
            serialized = self._canonical_json(data)
            if self._approx_distance(serialized, str(self._anchor.identity)) < self.delta_fp:
                return self._anchor.identity
            return serialized

        return data

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.lower().strip().split())

    def _canonical_text(self, text: str) -> str:
        if not text:
            return text
        tokens = text.split()
        return " ".join(tokens)

    def _canonical_json(self, value: Any) -> str:
        try:
            from idicoc_notary_core.utils.hashing import canonical_json
            return canonical_json(value)
        except Exception:
            return repr(value)

    def _approx_distance(self, a: str, b: str) -> float:
        a_tokens = set(a.split())
        b_tokens = set(b.split())
        if not a_tokens or not b_tokens:
            return 1.0
        intersection = len(a_tokens & b_tokens)
        union = len(a_tokens | b_tokens)
        similarity = intersection / union
        return 1.0 - similarity
