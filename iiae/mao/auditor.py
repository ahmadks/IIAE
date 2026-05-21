"""MAO Auditing utilities — compare lexical baseline vs ML-integrated engines."""

import logging
from typing import Dict, List, Optional

from .contract import IMAOEngine, MAOReport

logger = logging.getLogger("IIAE.MAO.Auditor")


def _normalize_report(report: MAOReport) -> tuple:
    passed = bool(report.get("passed", False))
    score = float(report.get("score", 0.0) or 0.0)
    reason = str(report.get("reason", ""))
    return passed, score, reason


def compare_reports(
    primary_report: MAOReport,
    ai_report: MAOReport,
) -> Dict[str, object]:
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
    """Runs Annex V filters on two engines and surfaces divergences."""

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

    def audit_probability_entropy(
        self,
        response: str,
        rag_context: Optional[str] = None,
        axioms: Optional[List[str]] = None,
    ) -> Dict[str, object]:
        return self._compare(
            "probability_entropy", response, rag_context, axioms or []
        )

    def audit_axiomatic_invariance(self, axioms: list, response: str) -> Dict[str, object]:
        return self._compare("axiomatic_invariance", axioms, response)

    def audit_geoclimatic_synchrony(self, response: str, rag_context: str) -> Dict[str, object]:
        return self._compare("geoclimatic_synchrony", response, rag_context)

    def audit_concurrent_probability(
        self, response: str, rag_context: str, axioms: list
    ) -> Dict[str, object]:
        return self.audit_probability_entropy(response, rag_context, axioms)
