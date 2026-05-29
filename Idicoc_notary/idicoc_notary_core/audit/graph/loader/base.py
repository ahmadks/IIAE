from typing import Any, Dict, List, Protocol

class PolicyLoader(Protocol):
    """Interfaz para la carga de politicas externos al sistema."""

    def load_policies(self) -> List[Dict[str, Any]]:
        """
        Carga y devuelve una lista de diccionarios que representan politicas.
        Cada diccionario debe tener las claves requeridas por el PropertyGraph.
        """
        ...
