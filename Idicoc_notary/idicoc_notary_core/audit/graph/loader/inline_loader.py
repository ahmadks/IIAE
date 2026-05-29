from typing import Any, Dict, List

class InlinePolicyLoader:
    """Cargador de politicas en memoria (ideal para pruebas o configuración hardcodeada)."""

    def __init__(self, policies: List[Dict[str, Any]]) -> None:
        self.policies = policies

    def load_policies(self) -> List[Dict[str, Any]]:
        return self.policies
