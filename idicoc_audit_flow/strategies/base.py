from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple


class DissonanceStrategy(ABC):
    """Estrategia para calcular disonancia entre audit_input, context_input y context_axioms."""

    @abstractmethod
    def compute(
        self,
        audit_input: str,
        context_input: List[str],
        context_axioms: List[str],
        epsilon: float = 0.0,
        validate_conflicts: bool = False,
    ) -> Tuple[float, float, str, bool, Dict[str, Any]]:
        ...
