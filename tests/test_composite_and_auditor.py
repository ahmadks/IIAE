import pytest
from iiae.mao.composite import CompositeMAOEngine
from iiae.mao.contract import IMAOEngine
from iiae.mao.auditor import compare_reports

# Minimal dummy engine implementing IMAOEngine
class DummyEngine(IMAOEngine):
    def material_causality(self, response: str, rag_context: str) -> dict:
        return {"passed": True, "score": 1.0, "reason": None}

    def axiomatic_invariance(self, axioms: list, response: str) -> dict:
        return {"passed": True, "score": 1.0, "reason": None}

    def probability_entropy(self, response: str) -> dict:
        return {"passed": True, "score": 1.0, "reason": None}


def test_composite_engine_type_validation_raises():
    # non‑IMAOEngine primary should raise
    with pytest.raises(TypeError):
        CompositeMAOEngine(primary=object())
    # valid primary but invalid fallback should raise
    with pytest.raises(TypeError):
        CompositeMAOEngine(primary=DummyEngine(), fallback=object())


def test_compare_reports_detects_difference():
    primary_report = {"passed": True, "score": 0.85, "reason": "ok"}
    ai_report = {"passed": False, "score": 0.80, "reason": "mismatch"}
    audit = compare_reports(primary_report, ai_report)
    assert audit["consistent"] is False
    # Expect all three fields to differ
    assert set(audit["differences"]) == {"passed", "score", "reason"}
    # Verify normalized values are present
    assert audit["primary"]["passed"] is True
    assert audit["ai"]["passed"] is False
