from __future__ import annotations
from typing import Any, Dict, List, Optional


class PropertyGraph:
    """Estructura de grafo de propiedades para axiomas y reglas en el núcleo."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self._conflicts: List[Dict[str, Any]] = []

    def add_axiom(self, identifier: str, axiom: Dict[str, Any]) -> None:
        """Añade un axioma identificado al grafo."""
        self.nodes[identifier] = axiom

    def add_edge(self, source: str, target: str, relation: str) -> None:
        """Añade una arista entre dos axiomas."""
        self.edges.append({"source": source, "target": target, "relation": relation})

    def detect_conflicts(self) -> List[Dict[str, Any]]:
        """Detecta conflictos entre axiomas (simplificado: comprueba polarity)."""
        conflicts = []
        nodes_list = list(self.nodes.items())
        for i, (id1, axiom1) in enumerate(nodes_list):
            for id2, axiom2 in nodes_list[i+1:]:
                # Conflicto simple: dos axiomas sobre el mismo sujeto/objeto con polaridades opuestas
                if (axiom1.get("subject") == axiom2.get("subject") and
                    axiom1.get("object") == axiom2.get("object") and
                    axiom1.get("polarity") != axiom2.get("polarity")):
                    conflicts.append({
                        "axiom1": id1,
                        "axiom2": id2,
                        "reason": "opposite_polarity"
                    })
        self._conflicts = conflicts
        return conflicts

    def validate(self, raw_input: Any) -> bool:
        """Validación estructural básica; las implementaciones wrapper pueden especializarla."""
        # Validar contra conflictos activos: si hay conflictos, marcar como inválido (para testing)
        return len(self._conflicts) == 0

    def get_active_axioms(self) -> List[Dict[str, Any]]:
        """Retorna todos los axiomas activos."""
        return list(self.nodes.values())

    def get_conflicts(self) -> List[Dict[str, Any]]:
        """Retorna los últimos conflictos detectados."""
        return self._conflicts

    def compute_axiom_density(self) -> float:
        """Calcula la densidad de axiomas en el grafo."""
        if not self.nodes:
            return 0.0
        # Densidad = |E| / |V|^2 (normalizado a [0,1])
        num_nodes = len(self.nodes)
        num_edges = len(self.edges)
        max_edges = num_nodes * (num_nodes - 1) // 2
        if max_edges == 0:
            return 0.0
        return num_edges / max_edges

    def clear(self) -> None:
        """Limpia el grafo (para testing o reinicio)."""
        self.nodes.clear()
        self.edges.clear()
        self._conflicts.clear()
