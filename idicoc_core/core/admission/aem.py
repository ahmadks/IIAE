from __future__ import annotations
from typing import Any, Dict, List, Optional, Protocol
import datetime
from idicoc_utils.logger import get_logger

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

class AEMStorageBackend(Protocol):
    def save_entropy_event(self, event: Dict[str, Any]) -> None:
        ...
    def load_all_events(self) -> Dict[str, List[Dict[str, Any]]]:
        ...
    def clear(self) -> None:
        ...

class AnomalousEventManager:
    """
    AEM: Dominio de Aislamiento (Lead Shield).
    Implementación del filtro upstream que segrega ruido antes de la proyección canónica.
    """

    def __init__(self, property_graph: Any, analyzer: EntropyAnalyzer, threshold: float = 0.85, instance_name: str = "default_instance", storage_backend: Optional[AEMStorageBackend] = None):
        self._graph = property_graph
        self._analyzer = analyzer
        self._threshold = threshold
        self._instance_name = instance_name
        self._storage = storage_backend
        
        if self._storage is not None:
            self.entropy_map = self._storage.load_all_events()
            for key in ["DISCARDED_NOISE", "RECOVERABLE_NOISE", "ADMITTED"]:
                self.entropy_map.setdefault(key, [])
        else:
            # Mapa de Entropía para análisis forense (Sección 6.3)
            self.entropy_map = {
                "DISCARDED_NOISE": [],
                "RECOVERABLE_NOISE": [],
                "ADMITTED": [],
            }
        
        # Integración con el logger del framework
        self.logger = get_logger("admission.aem")

    def admit(self, raw_input: Any, hard_halt_on_breach: bool = False) -> tuple[Any, dict]:
        """
        Gatekeeper del pipeline:
        1. Descompone la entrada en componente estructural y ruido.
        2. Evalúa el nivel de entropía del ruido.
        3. Segrega si es necesario.
        4. Clasifica entre ruido descartable (ηₛ) o recuperable (ηᵣ).
        """
        structural_component, noise_component = self._analyzer.decompose(raw_input)
        entropy_score = self._analyzer.measure_entropy(noise_component if noise_component is not None else raw_input)
        structural_complexity = self._compute_structural_complexity(structural_component)
        is_meaningful = self._is_structurally_meaningful(structural_component)
        within_barrier = self.entropy_barrier(entropy_score, structural_complexity)

        axiom_density = 0.0
        if hasattr(self._graph, "compute_axiom_density"):
            try:
                axiom_density = self._graph.compute_axiom_density()
            except Exception:
                pass

        if not is_meaningful or not within_barrier:
            noise_to_log = noise_component if noise_component is not None else raw_input
            if self._analyzer.is_recoverable(noise_to_log):
                category = "RECOVERABLE_NOISE"
            else:
                category = "DISCARDED_NOISE"
            self._log_noise(raw_input, category, entropy_score, structural_component, noise_to_log)
            metrics = {
                "entropy": entropy_score,
                "category": category,
                "admitted": False,
                "axiom_density": axiom_density,
                "structural": structural_component,
                "noise": noise_component,
            }
            if hard_halt_on_breach:
                raise AdmissionBreach(f"Entrada segregada: {category}")
            return structural_component, metrics

        metrics = {
            "entropy": entropy_score,
            "category": "ADMITTED",
            "admitted": True,
            "axiom_density": axiom_density,
            "structural": structural_component,
            "noise": noise_component,
        }
        if self._storage is not None:
            self._storage.save_entropy_event(metrics)
        else:
            self.entropy_map["ADMITTED"].append(metrics)
        return structural_component, metrics

    def entropy_barrier(self, entropy_score: float, structural_complexity: float = 0.0) -> bool:
        """
        Controla la barrera de entropía en función de la complejidad estructural.
        Simulación de delta_eta(S_c) del Anexo B.1.4.
        """
        delta_eta = min(0.5, 0.1 * structural_complexity)
        return entropy_score <= delta_eta

    def _compute_structural_complexity(self, structural_component: Any) -> float:
        graph_size = len(getattr(self._graph, "nodes", {}))
        rank = self._compute_rank(structural_component)
        depth = self._compute_graph_depth()
        alpha = 0.1
        beta = 0.2
        gamma = 0.6
        return alpha * graph_size + beta * rank + gamma * depth

    def _compute_rank(self, structural_component: Any) -> float:
        if isinstance(structural_component, str):
            return float(len(structural_component.split()))
        if isinstance(structural_component, dict):
            return float(len(structural_component))
        if isinstance(structural_component, (list, tuple, set)):
            return float(len(structural_component))
        return 1.0

    def _compute_graph_depth(self) -> float:
        if not hasattr(self._graph, "edges") or not self._graph.edges:
            return 1.0
        adjacency: dict[str, list[str]] = {}
        for edge in self._graph.edges:
            src = edge.get("source")
            tgt = edge.get("target")
            if src and tgt:
                adjacency.setdefault(src, []).append(tgt)
        visited: dict[str, int] = {}

        def dfs(node: str) -> int:
            if node in visited:
                return visited[node]
            max_depth = 1
            for child in adjacency.get(node, []):
                max_depth = max(max_depth, 1 + dfs(child))
            visited[node] = max_depth
            return max_depth

        return float(max(dfs(node) for node in adjacency) if adjacency else 1)

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
            "instance_name": self._instance_name,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        self.logger.warning(
            f"AEM Segregation Event: {category}",
            extra={"iiae_data": meta}
        )
        
        if self._storage is not None:
            self._storage.save_entropy_event(meta)
        else:
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