"""
IIAE vs MAO pipeline tests — Technical Annex V alignment.

IIAE (core): axioms, DQE, CTM, circuit breaker.
MAO (optional): four forensic filters via pluggable IMAOEngine.
"""

import time

import pytest

from iiae import IIAEConfig, audit, validate
from iiae.mao.auditor import MAOAuditor
from iiae.mao.filters import (
    MAOFilterConfig,
    axiomatic_invariance_filter,
    material_causality_filter,
)
from iiae.mao.lexical import LexicalMAOEngine
from iiae.mao.registry import register_engine, list_registered_engines
from iiae.supervisor import CircuitBreakerError, IIAESupervisor, IntegrityError

PROMPT = "What is the capital of France?"
RESPONSE = "France is a country in Europe. Its capital city is Paris."
CONTEXT = RESPONSE


def test_iiae_core_only_no_mao():
    """IIAE verifies integrity without MAO (enable_mao_filters=False)."""
    cfg = IIAEConfig(enable_mao_filters=False, ds_threshold=0.4)
    result = validate(PROMPT, RESPONSE, CONTEXT, config=cfg)

    assert result["verified"] is True
    assert result["ds"] == 0.0
    assert result["base_type"] == "Standard-Zero"
    assert result["mao"] == {}
    assert audit(receipt=result["receipt"]) is True


def test_iiae_with_lexical_mao_annex_v():
    """MAO optional: four Annex V filters via lexical engine."""
    cfg = IIAEConfig(
        enable_mao_filters=True,
        mao_engine_name="lexical",
        strict_mode=False,
    )
    result = validate(PROMPT, RESPONSE, CONTEXT, config=cfg)

    assert result["verified"] is True
    for key in (
        "material_causality",
        "probability_entropy",
        "axiomatic_invariance",
        "geoclimatic_synchrony",
    ):
        assert key in result["mao"]
        assert "metadata" in result["mao"][key]
        assert result["mao"][key]["metadata"]["origin_engine"] == "lexical"

    assert result["mao"]["material_causality"]["passed"] is True


def test_full_pipeline_lexical():
    cfg = IIAEConfig(
        enable_mao_filters=True,
        mao_engine_name="lexical",
        strict_mode=False,
    )
    result = validate(PROMPT, RESPONSE, CONTEXT, config=cfg)

    assert result["verified"] is True
    assert result["ds"] == 0.0
    assert audit(receipt=result["receipt"]) is True


def test_axiomatic_data_loss_detected():
    cfg = MAOFilterConfig(axiom_preservation_threshold=0.8)
    report = axiomatic_invariance_filter(
        ["Security protocols must always remain active and enforced."],
        "Security is disabled.",
        config=cfg,
    )
    assert report["passed"] is False


def test_mao_auditor_lexical_consistency():
    lex_a = LexicalMAOEngine()
    lex_b = LexicalMAOEngine()
    auditor = MAOAuditor(lex_a, lex_b)
    audit_report = auditor.audit_material_causality(RESPONSE, CONTEXT)
    assert audit_report["consistent"] is True


def test_ctm_integrity_tamper_detection():
    result = validate(PROMPT, RESPONSE, CONTEXT)
    receipt = result["receipt"]
    assert audit(receipt=receipt) is True
    receipt["payload"]["ds"] = 999
    assert audit(receipt=receipt) is False


def test_circuit_breaker_open_half_open():
    cfg = IIAEConfig(
        ds_threshold=0.0,
        max_trips=1,
        cb_cooldown_ms=100,
        strict_mode=True,
        enable_mao_filters=False,
    )
    supervisor = IIAESupervisor(config=cfg)

    with pytest.raises(IntegrityError):
        supervisor.verify("p", "wrong answer with no overlap", CONTEXT)
    with pytest.raises(IntegrityError):
        supervisor.verify("p", "another wrong answer", CONTEXT)
    with pytest.raises(CircuitBreakerError):
        supervisor.verify("p", "wrong again", CONTEXT)

    time.sleep(0.15)
    state = supervisor.verify(PROMPT, RESPONSE, CONTEXT)
    assert state.ds == 0.0


class CopilotSemanticMAOStub(LexicalMAOEngine):
    def geoclimatic_synchrony(self, response: str, rag_context: str) -> dict:
        report = super().geoclimatic_synchrony(response, rag_context)
        report["metadata"] = {"origin": "copilot_semantic_stub"}
        return report


def test_enterprise_copilot_style_integration():
    if "copilot_semantic_stub" not in list_registered_engines():
        register_engine("copilot_semantic_stub", CopilotSemanticMAOStub)

    cfg = IIAEConfig(
        enable_mao_filters=True,
        mao_engine_name="copilot_semantic_stub",
        strict_mode=False,
    )
    result = validate(PROMPT, RESPONSE, CONTEXT, config=cfg)
    assert result["verified"] is True

    auditor = MAOAuditor(LexicalMAOEngine(), CopilotSemanticMAOStub())
    cross = auditor.audit_material_causality(RESPONSE, CONTEXT)
    assert cross["consistent"] is True


try:
    import sentence_transformers  # noqa: F401
    import torch  # noqa: F401
    _HAS_SEMANTIC_DEPS = True
except ImportError:
    _HAS_SEMANTIC_DEPS = False


@pytest.mark.skipif(not _HAS_SEMANTIC_DEPS, reason="optional semantic deps not installed")
def test_full_pipeline_semantic_optional():
    from examples.mao.semantic_mao_engine import ExampleSemanticMAOEngine

    if "example_semantic" not in list_registered_engines():
        register_engine("example_semantic", ExampleSemanticMAOEngine)

    # Use lenient thresholds for testing semantic engine integration
    cfg = IIAEConfig(
        enable_mao_filters=True,
        mao_engine_name="example_semantic",
        strict_mode=False,
        mao_engine_params={
            "entailment_threshold": 0.0,  # Lenient for test
        }
    )
    result = validate(PROMPT, RESPONSE, CONTEXT, config=cfg)
    assert result["verified"] is True
    assert result["mao"]["material_causality"]["passed"] is True
