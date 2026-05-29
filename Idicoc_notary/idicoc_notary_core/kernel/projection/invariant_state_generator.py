# idicoc_notary_core/kernel/projection/invariant_state_generator.py
from __future__ import annotations
from typing import Any, Dict
from datetime import datetime, timezone

import numpy as np

from idicoc_notary_core.kernel.exceptions.integrity_breach import InvariantStateBreach
from idicoc_notary_core.kernel.source.anchor import SourceAnchor
from idicoc_notary_core.kernel.verification.registry import ProjectionRegistry
from idicoc_notary_core.utils.logger import get_logger


class CanonicalState:
    """Representación formal del estado canónico V_hat generado por el ISG.

    ===========================================================================

    Este objeto representa el "estado ideal y definitivo" (un vector numérico)
    al que se ha reducido la petición del usuario tras procesarla y estabilizarla.
    Es el valor de referencia matemática que usaremos para comparar el resto de
    operaciones y medir desviaciones.
    ===========================================================================

    Attributes:
        measure_vector (np.ndarray): Vector numérico que contiene la representación latente.
        metadata (dict): Metadatos del pipeline asociados a la generación (timestamps, trazas).
        is_canonical (bool): Flag constante que valida la naturaleza del estado.

    Examples:
        >>> from idicoc_notary_core.kernel.projection.invariant_state_generator import CanonicalState
        >>> state = CanonicalState(measure_vector=[0.1, 0.9], metadata={"timestamp": "2026-05-28"})
        >>> print(state.is_canonical)
        True
        >>> print(state.semantic_vector)
        [0.1, 0.9]
    """

    def __init__(self, measure_vector: Any, metadata: Dict):
        self.measure_vector = measure_vector
        self.metadata = metadata
        self.is_canonical = True

    def get_representation(self, preference: str = "measure") -> Any:
        return self.measure_vector

    @property
    def semantic_vector(self) -> Any:
        """Alias de compatibilidad para d_inv y aserciones de pruebas."""
        return self.measure_vector

    def __str__(self) -> str:
        payload = self.get_representation()
        return str(payload)

    def __repr__(self) -> str:
        return f"CanonicalState(measure_vector={self.measure_vector!r}, metadata={self.metadata!r})"


class InvariantStateGenerator:
    """MAII-ISG — Canonical Invariant State Generator.

    Convierte el input del sistema en su estado canónico V_hat. El ISG
    obtiene una representación numérica del input y la preserva como estado
    canónico. No se normaliza ni se escala el vector en esta etapa, de modo
    que la magnitud informativa de la señal se conserva.

    K no entra como referencia numérica. El ISG no compara contra K.

    Attributes:
        _anchor (SourceAnchor): Marcador estructural de K (sin valor numérico).
        _registry (ProjectionRegistry): Registro de proyecciones previas.
        config (AuditConfig, optional): Configuración global del auditor.

    Raises:
        InvariantStateBreach: Si falla la proyección canónica.

    Examples:
        >>> from idicoc_notary_core.kernel.projection.invariant_state_generator import InvariantStateGenerator
        >>> from idicoc_notary_core.kernel.source.anchor import SourceAnchor
        >>> from idicoc_notary_core.kernel.verification.registry import ProjectionRegistry
        >>> anchor = SourceAnchor()
        >>> registry = ProjectionRegistry()
        >>> isg = InvariantStateGenerator(anchor, registry)
    """

    def __init__(
        self,
        anchor: Any,
        registry: ProjectionRegistry,
        require_embedding_model: bool = False,
        config: Any = None,
    ):
        import threading

        self._anchor = anchor  # k (coálgebra terminal)
        self._registry = registry  # registro de proyecciones previas (no politicas)
        self.require_embedding_model = require_embedding_model
        self.config = config
        self.logger = get_logger("kernel.isg")
        self._fallback_count = 0
        self._fallback_lock = threading.Lock()

    def generate(self, admitted_input: Any) -> CanonicalState:
        """
        Construye el estado canónico V_hat del ISG aplicando el Policya de Unicidad.
        """
        try:
            v_hat = self._project_to_invariant(admitted_input)
        except Exception as e:
            raise InvariantStateBreach(
                message="Fallo en la proyección canónica (MAII‑ISG).",
                invalid_state=admitted_input,
                context={"error": str(e)},
                origin="MAII‑ISG.generate",
            )

        with self._fallback_lock:
            current_fallbacks = self._fallback_count

        metadata = {
            "stage": "MAII‑ISG",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "projection_history": self._registry.get_projection_trace(),
            "embedding_fallback_incidents": current_fallbacks,
        }

        return CanonicalState(
            measure_vector=v_hat,
            metadata=metadata,
        )

    def _project_to_invariant(self, data: Any) -> Any:
        """
        Operador de contracción hacia la estructura invariante.
        """
        vector: Any = None
        if isinstance(data, CanonicalState):
            return data.get_representation()

        if hasattr(data, "data") and not isinstance(data, np.ndarray):
            return self._project_to_invariant(data.data)

        if hasattr(data, "distribution") and not isinstance(data, np.ndarray):
            return self._project_to_invariant(data.distribution)

        # ── Caso topológico estándar: input numérico/vectorial ───────────────
        vector = None
        is_collapsed = False
        dist = 0.0

        if isinstance(data, np.ndarray):
            vector = np.asarray(data, dtype=float)
        elif isinstance(data, (list, tuple)) and all(
            isinstance(item, (int, float)) for item in data
        ):
            vector = np.asarray(data, dtype=float)
        elif isinstance(data, str):
            normalized = self._normalize_text(data)
            vector = self._text_to_vector(normalized)
        elif isinstance(data, (dict, list)):
            canonical_json_str = self._canonical_json(data)
            vector = self._text_to_vector(canonical_json_str)
        else:
            vector = self._text_to_vector(repr(data))

        # No se normaliza el embedding en esta etapa. La magnitud del vector
        # se conserva de forma íntegra para respetar la semántica de la señal.
        dist = 0.0
        is_collapsed = False

        try:
            from idicoc_notary_core.utils.hashing import sha256_hex, canonical_json

            state_hash = sha256_hex(
                canonical_json(vector.tolist() if isinstance(vector, np.ndarray) else vector)
            )
        except Exception:
            state_hash = ""

        self._registry.register_projection(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "original_input_type": type(data).__name__,
                "structural_deviation": dist,
                "collapsed_to_stable_form": is_collapsed,
                "canonical_state_hash": state_hash,
            }
        )

        return vector

    def _text_to_vector(self, text: str) -> np.ndarray:
        """Convierte texto a vector mediante embedding.

        No depende del anchor — K no tiene dimensión.
        """
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        if getattr(self.config, "semantic_embedding_model", None) is not None:
            model_name = self.config.semantic_embedding_model

        if self.require_embedding_model:
            from idicoc_notary_core.utils.string_utils import StringUtils

            if StringUtils.get_embedding_model(model_name) is None:
                raise InvariantStateBreach(
                    message="Modelo de embedding obligatorio no disponible.",
                    invalid_state=text,
                    origin="MAII-ISG._text_to_vector",
                )

        try:
            from idicoc_notary_core.utils.string_utils import StringUtils

            max_chunks = getattr(self.config, "embedding_max_chunks", 10)
            vector = StringUtils.embed_text(
                text,
                model_name=model_name,
                max_chunks=max_chunks,
            )
            return vector
        except InvariantStateBreach:
            raise
        except Exception as exc:
            self.logger.error(
                f"Degradación del servicio de embeddings detectada: {exc}. "
                "Activando fallback numérico determinista offline (MAII-ISG).",
                exc_info=exc,
            )
            with self._fallback_lock:
                self._fallback_count += 1

            if self.require_embedding_model:
                raise InvariantStateBreach(
                    message=f"Modelo de embedding obligatorio no disponible: {exc}",
                    invalid_state=text,
                    origin="MAII-ISG._text_to_vector",
                )
            # Fallback determinista — usar la dimensión del modelo si está disponible.
            dim = self._get_embedding_dim()
            vector = np.zeros(dim, dtype=float)
            for ch in text[:1000]:
                vector[ord(ch) % dim] += 1.0
            return vector

    def _get_embedding_dim(self) -> int:
        model_name = getattr(
            self.config, "semantic_embedding_model", "sentence-transformers/all-MiniLM-L6-v2"
        )
        try:
            from idicoc_notary_core.utils.string_utils import StringUtils

            model = StringUtils.get_embedding_model(model_name)
            if model is not None and hasattr(model, "get_sentence_embedding_dimension"):
                return int(model.get_sentence_embedding_dimension())
        except Exception:
            pass
        return 384

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
