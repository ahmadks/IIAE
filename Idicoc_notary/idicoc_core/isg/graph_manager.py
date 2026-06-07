from __future__ import annotations

import math
from typing import Any, Dict, List, Optional
import numpy as np


class PropertyGraph:
    """Estructura de grafo de propiedades para políticas y reglas en el núcleo."""

    def __init__(self, embedding_signature: Optional[str] = None) -> None:
        self.embedding_signature = embedding_signature
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: List[Dict[str, Any]] = []
        self._conflicts: List[Dict[str, Any]] = []

    def add_policy(self, identifier: str, policy: Dict[str, Any]) -> None:
        """Añade una política identificada al grafo."""
        self.nodes[identifier] = policy

    def add_edge(self, source: str, target: str, relation: str) -> None:
        """Añade una arista entre dos políticas."""
        self.edges.append({"source": source, "target": target, "relation": relation})

    def detect_conflicts(self) -> List[Dict[str, Any]]:
        """Detecta conflictos entre políticas (comprueba polarity en mismo sujeto/objeto)."""
        conflicts = []
        nodes_list = list(self.nodes.items())
        for i, (id1, policy1) in enumerate(nodes_list):
            for id2, policy2 in nodes_list[i + 1:]:
                if (
                    policy1.get("subject") == policy2.get("subject")
                    and policy1.get("object") == policy2.get("object")
                    and policy1.get("polarity") != policy2.get("polarity")
                ):
                    conflicts.append({"policy1": id1, "policy2": id2, "reason": "opposite_polarity"})
        self._conflicts = conflicts
        return conflicts

    def validate(self, raw_input: Any) -> bool:
        """Validación estructural básica."""
        return len(self._conflicts) == 0

    def project_to_manifold(self, input_vector: np.ndarray) -> np.ndarray:
        """
        Projects the input vector onto the policy graph manifold.
        """
        active_policies = self.get_active_policies()
        if not active_policies or input_vector.size == 0:
            return input_vector

        policy_vectors = []
        for p in active_policies:
            emb = p.get("embedding")
            if emb is not None:
                policy_vectors.append(np.asarray(emb, dtype=float))

        if not policy_vectors:
            return input_vector

        projected = input_vector.copy()
        for pv in policy_vectors:
            norm_pv = np.linalg.norm(pv)
            if norm_pv > 1e-12:
                unit_pv = pv / norm_pv
                projected = projected - np.dot(projected, unit_pv) * unit_pv

        return projected

    def get_active_policies(self) -> List[Dict[str, Any]]:
        """Retorna todos los políticas activos."""
        return list(self.nodes.values())

    def get_conflicts(self) -> List[Dict[str, Any]]:
        """Retorna los últimos conflictos detectados."""
        return self._conflicts

    def compute_policy_density(self) -> float:
        """Calcula la densidad de políticas en el grafo."""
        if not self.nodes:
            return 0.0
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

    def to_dict(self) -> Dict[str, Any]:
        """
        Convierte el grafo en un diccionario canónico para serialización JSON.
        """
        nodes_dict = {}
        for nid, policy in self.nodes.items():
            ax_copy = dict(policy)
            if "embedding" in ax_copy and hasattr(ax_copy["embedding"], "tolist"):
                ax_copy["embedding"] = ax_copy["embedding"].tolist()
            nodes_dict[nid] = ax_copy

        return {
            "version": 1,
            "embedding_signature": self.embedding_signature,
            "nodes": nodes_dict,
            "edges": self.edges,
            "conflicts": self._conflicts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PropertyGraph":
        """Reconstruye el grafo desde un diccionario serializado."""
        graph = cls(embedding_signature=data.get("embedding_signature"))
        graph.nodes = data.get("nodes", {})
        graph.edges = data.get("edges", [])
        graph._conflicts = data.get("conflicts", [])
        return graph
