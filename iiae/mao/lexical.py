from .contract import IMAOEngine
from .filters import (
    material_causality_filter,
    axiomatic_invariance_filter,
    probability_filter,
)

class LexicalMAOEngine(IMAOEngine):
    """Lexical fallback implementation of the MAO engine.

    Uses simple heuristic filters defined in ``iiae.mao.filters``.
    """

    def material_causality(self, response: str, rag_context: str) -> dict:
        return material_causality_filter(response, rag_context)

    def axiomatic_invariance(self, axioms: list, response: str) -> dict:
        return axiomatic_invariance_filter(axioms, response)

    def probability_entropy(self, response: str) -> dict:
        return probability_filter(response)
