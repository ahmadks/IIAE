"""
Test file for IDICOCNotaryClient with semantic profile.
"""

from unittest.mock import MagicMock, patch, patch

import pytest
from idicoc_notary_core.audit.config import AuditConfig

from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient


def _build_semantic_service(compute_return):
    mock_strategy_class = MagicMock()
    mock_strategy_instance = MagicMock()
    mock_strategy_instance.compute.return_value = compute_return
    if isinstance(compute_return[0], list):
        mock_strategy_instance.compute_dissonance.side_effect = compute_return[0]
    else:
        mock_strategy_instance.compute_dissonance.return_value = compute_return[0]
    mock_strategy_instance._d_inv_from_pair = __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(return_value=0.0)
    mock_strategy_instance.lambda_weights = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    mock_strategy_class.lambda_weights = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    mock_strategy_class.return_value = mock_strategy_instance

    config = AuditConfig(dissonance_strategy=mock_strategy_class)
    config.rigidity_epsilon = 0.1
    config.dissonance_weights = (0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0)

    return IDICOCNotaryClient(config)


@pytest.fixture
def semantic_service():
    """Create an IDICOCNotaryClient instance configured for semantic mode."""
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

    with patch("idicoc_notary_core.kernel.graph.property_graph.PropertyGraph.evaluate", return_value=0.1):
        canonical_state = semantic_service.process_interaction(
            audit_input=audit_input,
            context_input=context_input,
            context_axioms=axiom_input,
            epsilon_override=None,
            trace_input="test_trace_structural",
            client_id="test_client_structural",
        )

    # Assertions
    assert canonical_state is not None
    print(f"DEBUG: canonical_state={canonical_state}")
    # No correction message expected
    assert "[SNAPPING ACTIVE]" not in canonical_state.data
    assert "[CRITICAL REJECTION]" not in canonical_state.data
    assert "[CRITICAL WRAPPER ERROR]" not in canonical_state.data

    metadata = canonical_state.metadata
    assert "algebraic_components" in metadata
    ac = metadata["algebraic_components"]
    assert "lambda_weights" not in ac

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
            [0.8, 0.05],
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
    print(f"DEBUG: semantic_meta={metadata}")
    correction_flag = metadata.get("correction_flag", False)
    assert correction_flag is True

    compliance = semantic_service.verify_compliance(canonical_state, tolerance=0.0)
    assert compliance is False
