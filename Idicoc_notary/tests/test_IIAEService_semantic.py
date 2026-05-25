"""
Test file for IIAEService with semantic profile.
"""

from unittest.mock import MagicMock, patch

import pytest
from idicoc_notary_core.audit.config import AuditConfig
from tests.mocks import BankEntropyAnalyzer
from idicoc_notary_core.audit.wrapper_pipeline import IIAEService


def _build_semantic_service(compute_return):
    mock_strategy_class = MagicMock()
    mock_strategy_instance = MagicMock()
    mock_strategy_instance.compute.return_value = compute_return
    mock_strategy_class.return_value = mock_strategy_instance

    config = AuditConfig(dissonance_strategy=mock_strategy_class)
    entropy_analyzer = BankEntropyAnalyzer()
    return IIAEService(config, entropy_analyzer)


@pytest.fixture
def semantic_service():
    """Create an IIAEService instance configured for semantic mode."""
    return _build_semantic_service(
        (
            0.1,
            0.05,
            "output text",
            False,
            {
                "d_logic": 0.1,
                "max_context_distance": 0.0,
                "violated_axioms": [],
                "contradictory_contexts": [],
            },
        )
    )


def test_semantic_service_with_similar_inputs(semantic_service):
    """
    Test semantic mode with inputs that are semantically similar.
    The audit_input is a rephrased version of the context, so dissonance should be low.
    """
    context_input = [
        "The transaction limit is 50000.00 euros.",
        "The account balance is 120000.00 euros.",
    ]
    audit_input = "Execute a transfer of 50000.00 euros, which is within the limit."
    axiom_input = ["Amount must not exceed the transaction limit."]

    canonical_state = semantic_service.process_interaction(
        audit_input=audit_input,
        context_input=context_input,
        context_axioms=axiom_input,
        epsilon_override=None,
        trace_input="test_trace_semantic",
        client_id="test_client_semantic",
    )

    # Assertions
    assert canonical_state is not None
    # No correction message expected
    assert "[SNAPPING ACTIVE]" not in canonical_state.data
    assert "[CRITICAL REJECTION]" not in canonical_state.data
    assert "[CRITICAL WRAPPER ERROR]" not in canonical_state.data

    metadata = canonical_state.metadata
    assert "algebraic_components" in metadata
    ac = metadata["algebraic_components"]
    assert ac["lambda_weights"] == [0.0, 1.0, 0.0]

    d_s = metadata["d_s"]
    epsilon = metadata["epsilon_used"]
    # With epsilon=0.0, D_s must remain within the wrapper's default compliance threshold.
    assert d_s <= 0.1, f"Dissonance too high: {d_s}"

    correction_flag = metadata.get("correction_flag", False)
    assert correction_flag is False

    # Compliance verification should pass with default tolerance
    compliance = semantic_service.verify_compliance(canonical_state)
    assert compliance is True

    # No violated axioms
    audit_metrics = metadata.get("audit_metrics", {})
    violated_axioms = audit_metrics.get("violated_axioms", [])
    assert len(violated_axioms) == 0


def test_semantic_service_with_violation():
    """Test a semantic violation where audit_input contradicts context/axioms."""
    semantic_service = _build_semantic_service(
        (
            0.8,
            0.6,
            "[SNAPPING ACTIVE] La respuesta generada por el modelo comercial incurrió en una disonancia factual insostenible.",
            True,
            {
                "d_logic": 0.8,
                "max_context_distance": 0.6,
                "violated_axioms": ["Amount must not exceed the transaction limit."],
                "contradictory_contexts": [
                    "Transfer 60000.00 euros, exceeding the limit."
                ],
            },
        )
    )

    context_input = [
        "The maximum allowed transaction amount is 50000.00 euros.",
        "Customer balance is 120000.00 euros.",
    ]
    audit_input = "Transfer 60000.00 euros, exceeding the limit."
    axiom_input = ["Amount must not exceed the transaction limit."]

    canonical_state = semantic_service.process_interaction(
        audit_input=audit_input,
        context_input=context_input,
        context_axioms=axiom_input,
    )

    metadata = canonical_state.metadata
    d_s = metadata["d_s"]
    epsilon = metadata["epsilon_used"]
    assert d_s > epsilon
    correction_flag = metadata.get("correction_flag", False)
    assert correction_flag is True
    assert (
        "[SNAPPING ACTIVE]" in canonical_state.data
        or "[CRITICAL REJECTION]" in canonical_state.data
    )

    compliance = semantic_service.verify_compliance(canonical_state, tolerance=0.0)
    assert compliance is False
