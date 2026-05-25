# idicoc_notary_core/kernel/projection/invariant_state_generator.py
from __future__ import annotations
from typing import Any, Dict
from datetime import datetime, timezone

from idicoc_notary_core.kernel.exceptions.integrity_breach import InvariantStateBreach
from idicoc_notary_core.kernel.source.anchor import SourceAnchor
from idicoc_notary_core.kernel.verification.registry import ProjectionRegistry


class CanonicalState:
    """
    Representación formal del estado invariante V^t.
    Contiene dos proyecciones complementarias:
      - semantic_vector: ruta semántica/textual para estrategias basadas en significado.
      - measure_vector: ruta métrica para estrategias basadas en medidas numéricas.
    """

    def __init__(self, semantic_vector: Any, measure_vector: Any, metadata: Dict):
        self.semantic_vector = semantic_vector
        self.measure_vector = measure_vector
        self.metadata = metadata
        self.is_canonical = True

    def get_representation(self, preference: str = "semantic") -> Any:
        if preference == "measure":
            return self.measure_vector if self.measure_vector is not None else self.semantic_vector
        return self.semantic_vector if self.semantic_vector is not None else self.measure_vector

    def __str__(self) -> str:
        payload = self.get_representation("semantic")
        return str(payload)

    def __repr__(self) -> str:
        return (
            f"CanonicalState(semantic_vector={self.semantic_vector!r}, "
            f"measure_vector={self.measure_vector!r}, metadata={self.metadata!r})"
        )


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
            semantic_projection = self._project_to_invariant(admitted_input)
            measure_projection = self._project_to_measure(admitted_input)
        except Exception as e:
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

        return CanonicalState(
            semantic_vector=semantic_projection,
            measure_vector=measure_projection,
            metadata=metadata,
        )

    def _project_to_invariant(self, data: Any) -> Any:
        """
        Operador de contracción hacia la estructura invariante.

        En la ontología monaxiomática:
            f_ISG(data) → V^t

        Se aplica una normalización básica y un colapso por tolerancia δ_fp.
        """
        if isinstance(data, CanonicalState):
            return data.get_representation("semantic")

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

    def _project_to_measure(self, data: Any) -> list[float]:
        if isinstance(data, CanonicalState):
            return data.get_representation("measure")

        if hasattr(data, "data"):
            return self._project_to_measure(data.data)

        if isinstance(data, str):
            normalized = self._normalize_text(data)
            return [float(len(normalized)), float(len(set(normalized.split())))]

        if isinstance(data, dict) or isinstance(data, list):
            serialized = self._canonical_json(data)
            return [float(len(serialized)), float(len(set(serialized.split())))]

        if isinstance(data, (list, tuple, set)):
            return [float(len(data))]

        try:
            return [float(data)]
        except Exception:
            return [0.0]

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
