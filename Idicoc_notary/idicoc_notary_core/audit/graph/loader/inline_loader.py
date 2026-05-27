from typing import Any, Dict, List

class InlineAxiomLoader:
    """Cargador de axiomas en memoria (ideal para pruebas o configuración hardcodeada)."""

    def __init__(self, axioms: List[Dict[str, Any]]) -> None:
        self.axioms = axioms

    def load_axioms(self) -> List[Dict[str, Any]]:
        return self.axioms
