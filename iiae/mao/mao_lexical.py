from typing import Dict, Any
from iiae.mao.filters import material_causality_filter, axiomatic_invariance_filter, probability_filter

class LexicalMAOEngine:
    """Lexical fallback implementation of the MAO engine.

    It forwards calls to the existing filter functions defined in ``iiae.mao``.
    The return types match the expected ``Dict[str, Any]`` structure used by the
    supervisor.
    """

    def material_causality(self, response: str, rag_context: str) -> Dict[str, Any]:
        return material_causality_filter(response, rag_context)

    def axiomatic_invariance(self, axioms: list, response: str) -> Dict[str, Any]:
        return axiomatic_invariance_filter(axioms, response)

    def probability_entropy(self, response: str) -> Dict[str, Any]:
        return probability_filter(response)
