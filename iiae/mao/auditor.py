"""MAO Auditing utilities.

Provides a simple interface to compare the output of two MAO engines – typically the
lexical fallback engine and a custom AI‑based engine – and surface any discrepancies
as an audit report. This enables *self‑auditing* where developers can verify that a
more sophisticated engine does not diverge from the deterministic baseline.
"""

import logging
from typing import Tuple, Dict

from .contract import IMAOEngine, MAOReport

logger = logging.getLogger("IIAE.MAO.Auditor")


def _normalize_report(report: MAOReport) -> Tuple[bool, float, str]:
    """Return a canonical tuple (passed, score, reason) for comparison.

    The contract guarantees the keys ``passed``, ``score`` and ``reason`` – we
    defensively coerce missing keys to sensible defaults.
    """
    passed = bool(report.get("passed", False))
    score = float(report.get("score", 0.0) or 0.0)
    reason = str(report.get("reason", ""))
    return passed, score, reason


def compare_reports(
    primary_report: MAOReport,
    ai_report: MAOReport,
) -> Dict[str, object]:
    """Compare two MAO reports and return an audit dict.

    The function is deliberately lightweight – it does **not** raise exceptions.
    Instead it logs any divergence and returns a dictionary with the following
    structure:

    ```json
    {
        "consistent": <bool>,
        "primary": {"passed": ..., "score": ..., "reason": ...},
        "ai": {"passed": ..., "score": ..., "reason": ...},
        "differences": <list of field names that differ>
    }
    ```

    ``consistent`` is ``True`` when *all* three fields match exactly.
    """
    p_passed, p_score, p_reason = _normalize_report(primary_report)
    a_passed, a_score, a_reason = _normalize_report(ai_report)

    diffs = []
    if p_passed != a_passed:
        diffs.append("passed")
    if abs(p_score - a_score) > 1e-6:
        diffs.append("score")
    if p_reason != a_reason:
        diffs.append("reason")

    consistent = len(diffs) == 0
    if not consistent:
        logger.warning(
            "MAO audit mismatch: %s vs %s – differences: %s",
            primary_report,
            ai_report,
            diffs,
        )
    else:
        logger.info("MAO audit consistent between engines.")

    return {
        "consistent": consistent,
        "primary": {"passed": p_passed, "score": p_score, "reason": p_reason},
        "ai": {"passed": a_passed, "score": a_score, "reason": a_reason},
        "differences": diffs,
    }


class MAOAuditor:
    """Convenient wrapper that runs two engines and produces an audit report.

    Typical usage::

        auditor = MAOAuditor(lexical_engine, ai_engine)
        audit = auditor.audit_material_causality(response, rag_context)
        if not audit["consistent"]:
            # take corrective action
            pass
    """

    def __init__(self, primary: IMAOEngine, ai_engine: IMAOEngine):
        if not isinstance(primary, IMAOEngine):
            raise TypeError("primary must implement IMAOEngine")
        if not isinstance(ai_engine, IMAOEngine):
            raise TypeError("ai_engine must implement IMAOEngine")
        self._primary = primary
        self._ai = ai_engine

    def _compare(self, method_name: str, *args, **kwargs) -> Dict[str, object]:
        primary_report = getattr(self._primary, method_name)(*args, **kwargs)
        ai_report = getattr(self._ai, method_name)(*args, **kwargs)
        return compare_reports(primary_report, ai_report)

    def audit_material_causality(self, response: str, rag_context: str) -> Dict[str, object]:
        return self._compare("material_causality", response, rag_context)

    def audit_axiomatic_invariance(self, axioms: list, response: str) -> Dict[str, object]:
        return self._compare("axiomatic_invariance", axioms, response)

    def audit_probability_entropy(self, response: str) -> Dict[str, object]:
        return self._compare("probability_entropy", response)
