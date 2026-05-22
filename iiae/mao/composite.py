import logging
import uuid
from typing import Any, Dict, List, Optional
from .contract import IMAOEngine, MAOReport
from iiae.core.dse import PropertyGraph

logger = logging.getLogger("IIAE.MAO")


class CompositeMAOEngine(IMAOEngine):
    """Engine that delegates to a primary MAO engine and optionally a fallback.

    Ensures full traceability by attaching a trace_id and origin metadata
    to all reports, fulfilling the requirements for CTM (Custody Technical Metadata).
    """

    def __init__(self, primary: IMAOEngine, fallback: Optional[IMAOEngine] = None):
        if not isinstance(primary, IMAOEngine):
            raise TypeError("primary must implement IMAOEngine")
        if fallback is not None and not isinstance(fallback, IMAOEngine):
            raise TypeError("fallback must implement IMAOEngine")

        self._primary = primary
        self._fallback = fallback

    def _call(self, method_name: str, *args, **kwargs) -> Dict[str, Any]:
        """Internal helper to delegate and inject CTM metadata."""
        try:
            method = getattr(self._primary, method_name)
            result = method(*args, **kwargs)
            origin = "primary"
        except Exception as exc:
            logger.error(
                "Primary MAO engine failed in %s: %s", method_name, exc, exc_info=True
            )

            if self._fallback:
                method = getattr(self._fallback, method_name)
                result = method(*args, **kwargs)
                origin = "fallback"
            else:
                # Standard-Zero compliant failure report
                return {
                    "passed": False,
                    "score": 0.0,
                    "reason": f"Primary failure: {str(exc)}",
                    "metadata": {
                        "origin_engine": "failure",
                        "trace_id": uuid.uuid4().hex,
                    },
                }

        # Injection of Traceability Metadata
        result.setdefault("metadata", {})
        result["metadata"].update(
            {
                "origin_engine": origin,
                "trace_id": uuid.uuid4().hex,
            }
        )
        return result

    def material_causality(self, response: str, rag_context: str) -> Dict[str, Any]:
        return self._call("material_causality", response, rag_context)

    def axiomatic_invariance(self, axioms: list, response: str) -> Dict[str, Any]:
        return self._call("axiomatic_invariance", axioms, response)

    def probability_entropy(
        self,
        response: str,
        rag_context: Optional[str] = None,
        axioms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self._call(
            "probability_entropy", response, rag_context or "", axioms or []
        )

    def evaluate_boundaries(self, response: str, graph: PropertyGraph) -> Dict[str, Any]:
        return self._call("evaluate_boundaries", response, graph)

    def geoclimatic_synchrony(self, response: str, rag_context: str) -> Dict[str, Any]:
        return self._call("geoclimatic_synchrony", response, rag_context)
