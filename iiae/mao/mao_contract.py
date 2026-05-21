from typing import Protocol, TypedDict, Dict, Any

class MAOReport(TypedDict, total=False):
    """Typed dict for MAO filter results.
    Keys are optional because different engines may provide a subset.
    """
    material_causality: Dict[str, Any]
    axiomatic_invariance: Dict[str, Any]
    probability_filter: Dict[str, Any]

class IMAOEngine(Protocol):
    """Interface for a MAO (Material‑Causality‑Opacity) engine.
    Implementations must be callable with the same signature as the legacy
    ``material_causality_filter`` etc. and return a ``MAOReport``.
    """

    def material_causality(self, response: str, rag_context: str) -> Dict[str, Any]: ...

    def axiomatic_invariance(self, axioms: list, response: str) -> Dict[str, Any]: ...

    def probability_entropy(self, response: str) -> Dict[str, Any]: ...
