from __future__ import annotations
from typing import Any, Dict, List, Optional, Protocol
import datetime
from idicoc_core.util.logger import get_logger

class EntropyAnalyzer(Protocol):
    """
    Interfaz agnóstica al sustrato para medir entropía.
    Implementar esta clase para cada sustrato (Neural, Firmware, Analog, etc).
    """
    def measure_entropy(self, raw_input: Any) -> float:
        """Retorna valor normalizado [0, 1]."""
        ...

    def decompose(self, raw_input: Any) -> tuple[Any, Optional[Any]]:
        """Descompone la entrada en componente estructural y ruido. Retorna (structural, noise)."""
        ...

    def is_recoverable(self, raw_input: Any) -> bool:
        """Determina si el ruido es recuperable (ηᵣ)."""
        ...

class AdmissionBreach(Exception):
    """Excepción lanzada cuando el AEM segrega una entrada."""
    pass

class AnomalousEventManager:
    """
    AEM: Dominio de Aislamiento (Lead Shield).
    Implementación del filtro upstream que segrega ruido antes de la proyección canónica.
    """

    def __init__(self, property_graph: Any, analyzer: EntropyAnalyzer, threshold: float = 0.85):
        self._graph = property_graph
        self._analyzer = analyzer
        self._threshold = threshold
        
        # Mapa de Entropía para análisis forense (Sección 6.3)
        self.entropy_map: Dict[str, List[Dict[str, Any]]] = {
            "DISCARDED_NOISE": [],
            "RECOVERABLE_NOISE": []
        }
        
        # Integración con el logger del framework
        self.logger = get_logger("admission.aem")

    def admit(self, raw_input: Any) -> Any:
        """
        Gatekeeper del pipeline:
        1. Descompone la entrada en componente estructural y ruido.
        2. Evalúa el nivel de entropía del ruido.
        3. Segrega si es necesario.
        4. Clasifica entre ruido descartable (ηₛ) o recuperable (ηᵣ).
        """
        structural_component, noise_component = self._analyzer.decompose(raw_input)
        entropy_score = self._analyzer.measure_entropy(noise_component if noise_component is not None else raw_input)
        axiom_density = self._graph.compute_axiom_density() if hasattr(self._graph, "compute_axiom_density") else 0.0

        if self._is_structurally_meaningful(structural_component) and self.entropy_barrier(entropy_score, axiom_density):
            return structural_component

        noise_to_log = noise_component if noise_component is not None else raw_input
        if self._analyzer.is_recoverable(noise_to_log):
            self._log_noise(raw_input, "RECOVERABLE_NOISE", entropy_score, structural_component, noise_to_log)
            raise AdmissionBreach("Entrada segregada: Ruido recuperable (ηᵣ).")
        else:
            self._log_noise(raw_input, "DISCARDED_NOISE", entropy_score, structural_component, noise_to_log)
            raise AdmissionBreach("Entrada segregada: Ruido estructural descartado (ηₛ).")

    def entropy_barrier(self, entropy_score: float, structural_complexity: float = 0.0) -> bool:
        """
        Controla la barrera de entropía en función del umbral y la complejidad estructural.
        Simulación de delta_eta(S_c) del Anexo B.1.4.
        """
        complexity_penalty = min(0.2, structural_complexity * 0.05)
        effective_threshold = self._threshold + complexity_penalty
        return entropy_score <= effective_threshold

    def _is_structurally_meaningful(self, structural_component: Any) -> bool:
        """Verificación de coherencia con el Property Graph (G_t)."""
        if hasattr(self._graph, "validate"):
            try:
                return self._graph.validate(structural_component)
            except Exception:
                return False
        return True

    def _log_noise(
        self,
        raw_input: Any,
        category: str,
        entropy_score: float,
        structural_component: Any,
        noise_component: Any,
    ) -> None:
        """
        Registra el evento de segregación usando el logger de IIAE con información forense completa.
        Los datos se envían a través de 'iiae_data' para el JSONFormatter (Sección 6.3).
        """
        meta = {
            "category": category,
            "entropy_score": entropy_score,
            "origin_snippet": str(raw_input)[:50],
            "raw_size": len(str(raw_input)),
            "structural_component_snippet": str(structural_component)[:50],
            "structural_size": len(str(structural_component)),
            "noise_snippet": str(noise_component)[:50] if noise_component is not None else None,
            "noise_size": len(str(noise_component)) if noise_component is not None else 0,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        self.logger.warning(
            f"AEM Segregation Event: {category}",
            extra={"iiae_data": meta}
        )
        
        self.entropy_map[category].append(meta)

    def compute_epr(self) -> float:
        """
        Calcula el Entropy Purge Rate (EPR) para métricas de eficiencia (Sección 6.5).
        EPR = ηₛ / (ηₛ + ηᵣ)
        """
        eta_s = len(self.entropy_map["DISCARDED_NOISE"])
        eta_r = len(self.entropy_map["RECOVERABLE_NOISE"])
        
        total = eta_s + eta_r
        if total == 0:
            return 1.0
            
        return eta_s / total