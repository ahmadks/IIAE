from __future__ import annotations
from typing import Any, Dict, List, Optional

from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph


class AxiomEngine:
    """Motor de gestión de axiomas que inyecta invariantes en el PropertyGraph."""

    def __init__(self, axioms: Optional[List[Dict[str, Any]]] = None) -> None:
        self.axioms = axioms or []

    def provision_graph(self, graph: PropertyGraph) -> None:
        for idx, axiom in enumerate(self.axioms):
            if isinstance(axiom, dict):
                identifier = axiom.get("id") or f"axiom_{idx}"
            else:
                identifier = f"axiom_{idx}"
                axiom = {"text": str(axiom)}
            graph.add_axiom(identifier, axiom)

    def render_axioms(self, graph: PropertyGraph) -> List[str]:
        active_axioms = graph.get_active_axioms()
        return [self._render_axiom(axiom) for axiom in active_axioms]

    @staticmethod
    def _render_axiom(axiom: Any) -> str:
        if isinstance(axiom, str):
            return axiom
        if isinstance(axiom, dict):
            return (
                axiom.get("text")
                or axiom.get("statement")
                or axiom.get("description")
                or str(axiom)
            )
        return str(axiom)
