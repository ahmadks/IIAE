import logging
from .contract import IMAOEngine, MAOReport

logger = logging.getLogger("IIAE.MAO")

class CompositeMAOEngine(IMAOEngine):
    """Engine that delegates to a primary MAO engine and optionally a fallback.

    If the primary engine raises an exception, the error is logged (including the
    exception message) and the fallback is used. If no fallback is provided, a
    safe default ``{"passed": False, "score": 0.0, "reason": ...}`` dict is
    returned so that callers always receive a dict compatible with ``MAOReport``.
    """

    def __init__(self, primary: IMAOEngine, fallback: IMAOEngine | None = None):
        # Ensure engines conform to the IMAOEngine protocol
        if not isinstance(primary, IMAOEngine):
            raise TypeError("primary must implement IMAOEngine")
        if fallback is not None and not isinstance(fallback, IMAOEngine):
            raise TypeError("fallback must implement IMAOEngine when provided")
        self._primary = primary
        self._fallback = fallback

    def _call(self, method_name: str, *args, **kwargs) -> dict:
        try:
            method = getattr(self._primary, method_name)
            return method(*args, **kwargs)
        except Exception as exc:  # pragma: no cover – exercised via tests
            logger.error(
                "Primary MAO engine failed in %s: %s", method_name, exc, exc_info=True
            )
            if self._fallback:
                # Use fallback engine transparently
                return getattr(self._fallback, method_name)(*args, **kwargs)
            # Return a Standard‑Zero compliant failure report with explicit cause
            return {"passed": False, "score": 0.0, "reason": f"Primary failure: {exc}"}

    def material_causality(self, response: str, rag_context: str) -> dict:
        return self._call("material_causality", response, rag_context)

    def axiomatic_invariance(self, axioms: list, response: str) -> dict:
        return self._call("axiomatic_invariance", axioms, response)

    def probability_entropy(self, response: str) -> dict:
        return self._call("probability_entropy", response)
