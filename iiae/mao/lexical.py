from typing import Any, List, Optional

from .contract import IMAOEngine
from .filters import (
    MAOFilterConfig,
    axiomatic_invariance_filter,
    concurrent_probability_filter,
    geoclimatic_synchrony_filter,
    material_causality_filter,
)
from .report import enrich_report
from iiae.core.dse import PropertyGraph

ORIGIN_ENGINE = "lexical"


class LexicalMAOEngine(IMAOEngine):
    """Deterministic lexical fallback for Annex V filters (no locale / no ML)."""

    def __init__(self, **params: Any) -> None:
        self._origin = params.get("origin_engine", ORIGIN_ENGINE)
        self._config = MAOFilterConfig(
            causality_threshold=float(params.get("causality_threshold", 0.20)),
            min_word_len=int(params.get("min_word_len", 4)),
            axiom_preservation_threshold=float(
                params.get("axiom_preservation_threshold", 0.50)
            ),
            borel_threshold=float(params.get("borel_threshold", 0.05)),
            enable_stemming=bool(params.get("enable_stemming", False)),
        )

    def _trace(self, report: dict, filter_name: str) -> dict:
        return enrich_report(
            report,
            origin_engine=self._origin,
            filter=filter_name,
        )

    def evaluate_boundaries(self, response: str, graph: PropertyGraph) -> dict:
        results = {
            "material_causality": self.material_causality(response, graph.source_text),
            "probability_entropy": self.probability_entropy(
                response, graph.source_text, graph.axioms
            ),
            "axiomatic_invariance": self.axiomatic_invariance(graph.axioms, response),
            "geoclimatic_synchrony": self.geoclimatic_synchrony(response, graph.source_text),
        }
        passed = all(r.get("passed", False) for r in results.values())
        results["passed"] = passed
        if not passed:
            results["reason"] = "manifold boundary violation"
        return results

    def material_causality(self, response: str, rag_context: str) -> dict:
        return self._trace(
            material_causality_filter(response, rag_context, self._config),
            "material_causality",
        )

    def concurrent_probability(
        self, response: str, rag_context: str, axioms: List[str]
    ) -> dict:
        return self._trace(
            concurrent_probability_filter(
                response, rag_context, axioms, self._config
            ),
            "probability_entropy",
        )

    def probability_entropy(
        self,
        response: str,
        rag_context: Optional[str] = None,
        axioms: Optional[List[str]] = None,
    ) -> dict:
        return self.concurrent_probability(
            response, rag_context or "", axioms or []
        )

    def axiomatic_invariance(self, axioms: list, response: str) -> dict:
        return self._trace(
            axiomatic_invariance_filter(axioms, response, self._config),
            "axiomatic_invariance",
        )

    def geoclimatic_synchrony(self, response: str, rag_context: str) -> dict:
        return self._trace(
            geoclimatic_synchrony_filter(response, rag_context),
            "geoclimatic_synchrony",
        )
