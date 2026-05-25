from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from idicoc_notary_core.audit.config import AuditConfig
    from idicoc_notary_core.kernel.projection.invariant_state_generator import CanonicalState
    from idicoc_notary_core.kernel.source.anchor import SourceAnchor


class DissonanceStrategy(ABC):
    """
    Interfaz abstracta para estrategias de cálculo de disonancia.
    
    Todas las implementaciones DEBEN devolver exactamente el mismo tipo de retorno
    con la misma estructura de métricas para garantizar compatibilidad con el pipeline.
    """

    def __init__(self, config: "AuditConfig") -> None:
        self.config = config

    @abstractmethod
    def compute(
        self,
        audit_input: Any,
        context_input: List[str],
        context_axioms: List[str],
        epsilon: float = 0.0,
        validate_conflicts: bool = False,
    ) -> Tuple[float, float, Any, bool, Dict[str, Any]]:
        """
        Compute dissonance metrics for the given audit input.
        
        TODAS las implementaciones deben devolver la misma estructura:
        
        Returns:
            Tuple[float, float, Any, bool, Dict[str, Any]] donde:
            - D_s (float): Dissonancia estructural [0, 1]
            - D_f (float): Dissonancia factual [0, 1]
            - corrected_output (Any): Salida corregida o audit_input original
            - correction_flag (bool): Si se aplicó corrección
            - metrics (Dict[str, Any]): Diccionario con TODOS estos campos REQUERIDOS:
                * 'd_s' (float): Dissonancia estructural
                * 'd_logic' (float): Dissonancia lógica máxima
                * 'd_factual' (float): Dissonancia factual
                * 'd_terminal' (float): Violación de coálgebra terminal
                * 'terminality_violation' (bool): Si hay violación terminal
                * 'max_axiom_distance' (float): Distancia máxima a axiomas
                * 'max_context_distance' (float): Distancia máxima a contexto
                * 'violated_axioms' (list[str]): Axiomas violados
                * 'contradictory_contexts' (list[str]): Contextos contradictorios
                * 'support_found' (bool): Si hay soporte en contexto
                * 'reference_count' (int): Cantidad de referencias totales
                * 'snapping_flag' (bool): Si se activó snapping fáctico
                * 'correction_flag' (bool): Si se aplicó corrección
        """
        ...

    @abstractmethod
    def select_canonical_input(self, canonical_state: "CanonicalState") -> Any:
        """
        Elige la representación canónica correcta para el eje de disonancia de la estrategia.
        """
        ...

    @abstractmethod
    def canonical_axis(self) -> str:
        """
        Devuelve el eje preferido para la estrategia: 'semantic' o 'measure'.
        """
        ...
