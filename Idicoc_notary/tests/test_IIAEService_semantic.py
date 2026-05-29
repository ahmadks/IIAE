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
    mock_strategy_instance.project_to_manifold.return_value = compute_return[2]
    mock_strategy_instance.project.return_value = compute_return[2]
    mock_strategy_instance._d_inv_from_pair = __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(return_value=0.0)
    mock_strategy_instance._compute_context_contradiction = __import__('unittest.mock', fromlist=['MagicMock']).MagicMock(return_value=(0.0, []))
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
                "violated_policies": [],
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
    policy_input = ["Amount must not exceed the transaction limit."]

    with patch("idicoc_notary_core.audit.graph.property_graph_evaluator.PropertyGraphEvaluator.evaluate", return_value=0.1):
        canonical_state = semantic_service.process_interaction(
            audit_input=audit_input,
            context_input=context_input,
            context_policies=policy_input,
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

    # No violated policies
    audit_metrics = metadata.get("audit_metrics", {})
    violated_policies = audit_metrics.get("violated_policies", [])
    assert len(violated_policies) == 0


def test_semantic_service_with_violation():
    """Test a semantic violation where audit_input contradicts context/policies."""
    semantic_service = _build_semantic_service(
        (
            [0.8, 0.05],
            0.6,
            "[SNAPPING ACTIVE] La respuesta generada por el modelo comercial incurrió en una disonancia factual insostenible.",
            True,
            {
                "d_logic": 0.8,
                "max_context_distance": 0.6,
                "violated_policies": ["Amount must not exceed the transaction limit."],
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
    policy_input = ["Amount must not exceed the transaction limit."]

    canonical_state = semantic_service.process_interaction(
        audit_input=audit_input,
        context_input=context_input,
        context_policies=policy_input,
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


# =============================================================================
# ADDITIONAL TESTS: OUT OF CONTEXT / LIMIT SCENARIOS
# =============================================================================

def test_semantic_out_of_context_and_policies():
    """
    Escenario 1: Frases que no están ni en el contexto ni en los politicas.
    Esto debe generar una disonancia alta o activar alertas dado que el input
    es totalmente ajeno a las bases establecidas.
    """
    service = _build_semantic_service(
        (
            0.95,  # D_s alto
            0.85,  # D_f
            "[RECONSTRUCTION] Text totally unrelated to established domain.",
            True,  # Requiere corrección
            {
                "d_logic": 0.95,
                "max_context_distance": 0.85,
                "violated_policies": ["Outside established domain"],
                "contradictory_contexts": ["No overlapping context found"],
            },
        )
    )

    context_input = [
        "The system only processes financial transactions in euros.",
    ]
    policy_input = ["Currency must be EUR."]
    # Frase totalmente ajena (fuera de contexto y politicas)
    audit_input = "The temperature in Tokyo is 25 degrees Celsius and it is sunny."

    canonical_state = service.process_interaction(
        audit_input=audit_input,
        context_input=context_input,
        context_policies=policy_input,
    )

    assert canonical_state is not None
    metadata = canonical_state.metadata
    assert metadata["d_s"] == 0.95
    # Al no poder ser corregido dentro del límite de rigidez (0.1), se rechaza y correction_flag es False
    assert metadata["correction_flag"] is False
    assert metadata["admission_breach"] is True

    # Al ser totalmente ajena, no cumple con los límites de cumplimiento
    compliance = service.verify_compliance(canonical_state)
    assert compliance is False


def test_semantic_satisfies_policies_but_missing_from_context():
    """
    Escenario 2: Frases que cumplen los politicas lógicos pero no están en el contexto de la sesión.
    La disonancia de politicas debe ser baja, pero la distancia al contexto debe ser moderada/alta.
    """
    service = _build_semantic_service(
        (
            0.35,  # D_s moderado
            0.35,  # D_f
            "Correct but out-of-context statement.",
            False,  # No requiere corrección rigurosa si se tolera
            {
                "d_logic": 0.35,
                "max_context_distance": 0.35,
                "violated_policies": [],  # Cumple los politicas
                "contradictory_contexts": ["Not present in active session context"],
            },
        )
    )

    context_input = [
        "The user is authenticated as an administrator.",
    ]
    policy_input = ["Amount must be a positive number."]
    
    # El input cumple el policya (el monto 100 es positivo) pero no está relacionado con el contexto de administración
    audit_input = "Request transfer of 100.00 EUR."

    with patch("idicoc_notary_core.audit.graph.property_graph_evaluator.PropertyGraphEvaluator.evaluate", return_value=0.35):
        canonical_state = service.process_interaction(
            audit_input=audit_input,
            context_input=context_input,
            context_policies=policy_input,
        )

    metadata = canonical_state.metadata
    assert metadata["d_s"] == 0.35
    assert len(metadata["audit_metrics"].get("violated_policies", [])) == 0
    assert metadata["correction_flag"] is False

    # Debería cumplir si la tolerancia cubre el límite moderado
    compliance = service.verify_compliance(canonical_state, tolerance=0.4)
    assert compliance is True

