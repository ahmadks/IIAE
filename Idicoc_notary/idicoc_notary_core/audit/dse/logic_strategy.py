# idicoc_notary_core/audit/logic_strategy.py
from __future__ import annotations
from typing import Any, Dict, List, Tuple, TYPE_CHECKING
import numpy as np

from idicoc_notary_core.kernel.admission.aem import AdmissionBreach
from .dissonance_strategy import DissonanceStrategy

# Importación diferida solo para tipado estático (evita dependencias circulares)
if TYPE_CHECKING:
    from idicoc_notary_core.audit.config import AuditConfig
    from idicoc_notary_core.kernel.source.anchor import SourceAnchor
    from idicoc_notary_core.kernel.projection.invariant_generator import CanonicalState


class LogicDissonanceStrategy(DissonanceStrategy):
    """
    Estrategia de auditoría lógica con rigidez paramétrica (delta_fp).
    Mide la divergencia estructural (Métrica de Kantorovich/EMD) contra el
    SourceAnchor inyectado dinámicamente, garantizando irrefutabilidad.
    """

    def __init__(self, config: AuditConfig, delta_fp: float | None = None) -> None:
        super().__init__(config)
        # La estrategia ya no "posee" la verdad. Solo guarda la tolerancia geométrica.
        self.delta_fp = delta_fp if delta_fp is not None else getattr(config, 'isg_delta_fp', 0.01)

    def _validate_input(self, audit_input: Any, expected_size: int) -> np.ndarray:
        """Valida que la entrada sea una medida compatible con el espacio del ancla."""
        try:
            measure = np.asarray(getattr(audit_input, "distribution", audit_input), dtype=float)
        except (ValueError, TypeError):
            raise AdmissionBreach("El input no es una señal numérica válida (incompatible con la Mónada de Giry).")
            
        if measure.size != expected_size:
            raise AdmissionBreach(
                f"Inconsistencia dimensional: La señal tiene dimensión {measure.size}, "
                f"pero el SourceAnchor requiere {expected_size}."
            )
        return measure

    def compute(
        self,
        audit_input: Any,
        context_input: List[str],
        context_axioms: List[str],
        epsilon: float = 0.0,
        validate_conflicts: bool = False,
    ) -> Tuple[float, float, Any, bool, Dict[str, Any]]:
        """
        Compute dissonance using optimal transport (Kantorovich EMD).
        
        The terminal reference (source_anchor) is obtained from self.config,
        not passed as a parameter. This encapsulates the source of truth
        within the strategy itself.
        """
        
        # 1. Extracción de la Verdad desde la configuración
        # (No como parámetro, sino como miembro del sistema)
        from idicoc_notary_core.kernel.source.anchor import SourceAnchor
        raw_k = getattr(self.config, 'constant_k', np.zeros(1, dtype=float))
        if not isinstance(raw_k, np.ndarray):
            raw_k = np.asarray(raw_k, dtype=float)
        source_anchor = SourceAnchor(raw_k)
        target_state = source_anchor.terminal_state
        
        # 2. Validación y Normalización de la entrada
        mu_raw = self._validate_input(audit_input, target_state.size)
        total = mu_raw.sum()
        # Normalizamos al simplex de probabilidad con estabilidad numérica
        mu = mu_raw / total if total > 1e-14 else np.ones_like(mu_raw) / mu_raw.size
        
        # 3. Cálculo de EMD (Transporte Óptimo de Kantorovich) con robustez
        # Distancia 1-Wasserstein: suma de diferencias de CDF
        cum_mu = np.cumsum(mu)
        cum_target = np.cumsum(target_state)
        
        # Clip a [0, 1] para evitar artefactos de punto flotante
        cum_mu = np.clip(cum_mu, 0.0, 1.0)
        cum_target = np.clip(cum_target, 0.0, 1.0)
        
        d_logic = float(np.sum(np.abs(cum_mu - cum_target)))
        lambda_logic = getattr(audit_input, "lambda_logic", 1.0)
        d_s = lambda_logic * d_logic
        
        # 4. Aplicación del Umbral Efectivo (Axioma de Rigidez)
        # El manifold admisible es D_s <= delta_fp + epsilon
        effective_threshold = self.delta_fp + epsilon
        is_compliant = d_s <= effective_threshold
        
        # 5. Estructuración de métricas
        metrics = {
            'd_s': d_s,
            'd_logic': d_logic,
            'effective_threshold': effective_threshold,
            'd_terminal': d_s,
            'terminality_violation': not is_compliant,
            'reference_count': int(mu.size),
            'correction_flag': not is_compliant
        }
        
        return (d_s, 0.0, audit_input, not is_compliant, metrics)

    def select_canonical_input(self, canonical_state: CanonicalState) -> np.ndarray:
        """Extrae el vector de medida (funtor F) del estado dual."""
        return canonical_state.measure_vector

    def canonical_axis(self) -> str:
        return "measure"