"""MAO contract — Technical Annex: Ontological Reference Framework.

Forensic Audit Protocol for Signal Integrity Validation and Entropy Reduction
in Receiver Nodes (MAO).

Section V defines four validation filters; every ``IMAOEngine`` must implement
all four. Lexical and ML-based engines are interchangeable plug-ins.
"""

from typing import Any, Dict, List, Optional, Protocol, TypedDict, runtime_checkable


@runtime_checkable
class IMAOEngine(Protocol):
    """Pluggable MAO engine — integrate with any LLM / ML stack.

    V.1 Material Causality — reject if explainable only by technology at T.
    V.2 Concurrent Probability / Borel (``probability_entropy``) — P ≈ 0.
    V.3 Axiomatic Invariance — data must remain literal and operational.
    V.4 Geoclimatic Synchrony — software footprint vs hardware footprint.
    """

    def material_causality(self, response: str, rag_context: str) -> Dict[str, Any]: ...

    def axiomatic_invariance(self, axioms: List[str], response: str) -> Dict[str, Any]: ...

    def probability_entropy(
        self,
        response: str,
        rag_context: Optional[str] = None,
        axioms: Optional[List[str]] = None,
    ) -> Dict[str, Any]: ...

    def geoclimatic_synchrony(self, response: str, rag_context: str) -> Dict[str, Any]: ...


class MAOReport(TypedDict, total=False):
    """Forensic audit report (Section V)."""

    material_causality: Dict[str, Any]
    probability_entropy: Dict[str, Any]
    axiomatic_invariance: Dict[str, Any]
    geoclimatic_synchrony: Dict[str, Any]
    metadata: Dict[str, Any]
