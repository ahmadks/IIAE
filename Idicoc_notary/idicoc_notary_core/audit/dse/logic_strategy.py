from __future__ import annotations
from typing import Any, Dict, List, Tuple, TYPE_CHECKING
import numpy as np
from typing import Any, Dict, List, Tuple
from idicoc_notary_core.audit.strategy import DissonanceStrategy
from idicoc_notary_core.kernel.admission.aem import AdmissionBreach # Ruta corregida

from .dissonance_strategy import DissonanceStrategy

if TYPE_CHECKING:
    from idicoc_notary_core.audit.config import AuditConfig
    from idicoc_notary_core.kernel.source.anchor import SourceAnchor


class LogicDissonanceStrategy(DissonanceStrategy):
    """
    Estrategia corregida con rigidez paramétrica (delta_fp).
    Mide la divergencia semántica contra la coalgebra terminal.
    """

    def __init__(self, config: "AuditConfig", terminal_state: np.ndarray, delta_fp: float = None) -> None:
        super().__init__(config)
        self.terminal_state = terminal_state
        # Usamos delta_fp del config si no se provee explícitamente
        self.delta_fp = delta_fp if delta_fp is not None else getattr(config, 'isg_delta_fp', 0.01)

    def _validate_input(self, audit_input: Any) -> np.ndarray:
        try:
            measure = np.asarray(getattr(audit_input, "distribution", audit_input), dtype=float)
        except (ValueError, TypeError):
            raise AdmissionBreach("Input no es una señal numérica válida (incompatible con Meas).")
            
        if measure.size != self.terminal_state.size:
            raise AdmissionBreach(f"Dimensión {measure.size} no coincide con el ancla {self.terminal_state.size}.")
        return measure

    def compute(
        self,
        audit_input: Any,
        context_input: List[str],
        context_axioms: List[str],
        source_anchor: "SourceAnchor",
        epsilon: float = 0.0,
        validate_conflicts: bool = False,
    ) -> Tuple[float, float, Any, bool, Dict[str, Any]]:
        
        # 1. Validación y Normalización
        mu_raw = self._validate_input(audit_input)
        total = mu_raw.sum()
        mu = mu_raw / total if total > 0 else np.ones_like(mu_raw) / mu_raw.size
        
        # 2. Cálculo de EMD (Kantorovich) y Disonancia
        lambda_logic = getattr(audit_input, "lambda_logic", 1.0)
        d_logic = float(np.sum(np.abs(np.cumsum(mu) - np.cumsum(self.terminal_state))))
        d_s = lambda_logic * d_logic
        
        # 3. Aplicación del Umbral Efectivo (Axioma de Rigidez)
        # El manifold admisible es D_s <= delta_fp + epsilon
        effective_threshold = self.delta_fp + epsilon
        is_compliant = d_s <= effective_threshold
        
        # 4. Métricas ajustadas al marco de rigidez
        metrics = {
            'd_s': d_s,
            'd_logic': d_logic,
            'effective_threshold': effective_threshold,
            'd_factual': 0.0,
            'd_terminal': d_s,
            'terminality_violation': not is_compliant,
            'max_axiom_distance': 0.0,
            'max_context_distance': 0.0,
            'violated_axioms': [],
            'contradictory_contexts': [],
            'support_found': True,
            'reference_count': int(mu.size),
            'snapping_flag': False,
            'correction_flag': not is_compliant
        }
        
        return (d_s, 0.0, audit_input, not is_compliant, metrics)