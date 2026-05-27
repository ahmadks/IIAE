from typing import Any, Dict, List, Protocol

class AxiomLoader(Protocol):
    """Interfaz para la carga de axiomas externos al sistema."""

    def load_axioms(self) -> List[Dict[str, Any]]:
        """
        Carga y devuelve una lista de diccionarios que representan axiomas.
        Cada diccionario debe tener las claves requeridas por el PropertyGraph.
        """
        ...
