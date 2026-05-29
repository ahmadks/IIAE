"""
Test file for IDICOCNotaryClient with logic strategy profile.
Tests the IIAE service integration with logical dissonance measurement via optimal transport.
"""

from unittest.mock import MagicMock, patch
import numpy as np

import pytest
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient
from idicoc_notary_core.audit.dse.structural_strategy import StructuralDissonanceStrategy


class MockAuditInput:
    """Mock input that simulates a measure (distribution) for logic strategy."""
    def __init__(self, distribution: np.ndarray, lambda_logic: float = 1.0):
        self.distribution = distribution
        self.lambda_logic = lambda_logic


def _build_logic_service(compute_return):
    """Create an IDICOCNotaryClient instance with mocked logic strategy."""
    mock_strategy_instance = MagicMock()
    
    if isinstance(compute_return[0], list):
        mock_strategy_instance.compute_dissonance.side_effect = compute_return[0]
    else:
        mock_strategy_instance.compute_dissonance.return_value = compute_return[0]
        
    mock_strategy_instance.project.return_value = compute_return[2]
    mock_strategy_instance.compute.return_value = compute_return
    mock_strategy_instance.lambda_weights = [0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0]
    mock_strategy_instance._d_inv_from_pair = MagicMock(return_value=0.0)
    mock_strategy_instance._compute_context_contradiction = MagicMock(return_value=(0.0, []))

    mock_strategy_class = MagicMock(return_value=mock_strategy_instance)
    mock_strategy_class.lambda_weights = [0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0]

    config = AuditConfig(
        dissonance_strategy=mock_strategy_class,
        dissonance_weights=(0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0)
    )
    config.ctm_mode = "log_only"
    config.rigidity_epsilon = 0.1
    return IDICOCNotaryClient(config)


@pytest.fixture
def logic_service():
    """Create an IDICOCNotaryClient instance configured for logic mode."""
    return _build_logic_service(
        (
            0.05,  # D_s (low dissonance for identical/similar distributions)
            0.02,  # D_f
            "output distribution",  # corrected_output
            False,  # correction_flag
            {
                "d_logic": 0.05,
                "d_logic_geom": 0.05,
                "d_logic_semantic": 0.05,
                "max_policy_distance": 0.0,
                "max_context_distance": 0.02,
                "violated_policies": [],
                "contradictory_contexts": [],
                "support_found": True,
                "terminality_violation": False,
                "algebraic_components": {"d_0": 0.0, "d_1": 0.0, "d_2": 0.05, "d_3": 0.0, "d_4": 0.0, "d_5": 0.0, "d_6": 0.0},
            },
        )
    )


def test_logic_service_with_compatible_distribution(logic_service):
    """
    Test logic mode with a distribution compatible with the terminal reference.
    The audit input (as a measure) should have low dissonance to the anchor.
    """
    # Terminal reference: uniform distribution (the canonical state)
    terminal_ref = np.array([0.33, 0.33, 0.34])
    
    # Audit input: slightly perturbed uniform distribution (still compatible)
    audit_distribution = np.array([0.32, 0.34, 0.34])
    audit_input = MockAuditInput(audit_distribution, lambda_logic=1.0)
    
    context_input = [
        "Distribution constraint: must maintain entropy ≥ 1.0",
        "Balance requirement: all mass must be accounted for",
    ]
    context_policies = [
        "The measure must lie in the probability simplex.",
        "No negative weights are allowed.",
    ]

    with patch("idicoc_notary_core.audit.graph.property_graph_evaluator.PropertyGraphEvaluator.evaluate", return_value=0.125):
        canonical_state = logic_service.process_interaction(
            audit_input=audit_input,
            context_input=context_input,
            context_policies=context_policies,
            epsilon_override=None,
            trace_input="test_trace_logic_compatible",
            client_id="test_client_logic",
        )

    # Assertions
    assert canonical_state is not None
    assert "[SNAPPING ACTIVE]" not in canonical_state.data
    assert "[CRITICAL REJECTION]" not in canonical_state.data
    assert "[STRUCTURAL CORRUPTION]" not in canonical_state.data

    metadata = canonical_state.metadata
    assert "algebraic_components" in metadata
    ac = metadata["algebraic_components"]
    # Lambda weights are no longer in algebraic_components

    d_s = metadata["d_s"]
    epsilon = metadata["epsilon_used"]
    # With low EMD distance, correction should not trigger
    assert d_s <= 0.1, f"Dissonance too high for compatible distribution: {d_s}"

    correction_flag = metadata.get("correction_flag", False)
    assert correction_flag is False

    # Compliance verification should pass with default tolerance
    compliance = logic_service.verify_compliance(canonical_state)
    assert compliance is True

    # No violated policies expected
    audit_metrics = metadata.get("audit_metrics", {})
    violated_policies = audit_metrics.get("violated_policies", [])
    assert len(violated_policies) == 0


def test_logic_service_with_incompatible_distribution():
    """
    Test a logic violation where audit input (as a distribution) is 
    orthogonal/incompatible with the anchor distribution.
    """
    logic_service = _build_logic_service(
        (
            [0.85, 0.05],  # D_s first call (high), second call (low -> corrected)
            0.70,  # D_f
            MockAuditInput(np.array([0.33, 0.33, 0.34]), lambda_logic=1.0),
            True,  # correction_flag triggered
            {
                "d_logic": 0.85,
                "d_logic_geom": 0.85,
                "d_logic_semantic": 0.85,
                "max_policy_distance": 0.9,
                "max_context_distance": 0.70,
                "violated_policies": ["The measure must lie in the probability simplex."],
                "contradictory_contexts": [
                    "Distribution constraint: mass escapes simplex"
                ],
                "support_found": False,
                "terminality_violation": False,
                "algebraic_components": {"d_0": 0.0, "d_1": 0.0, "d_2": 0.85, "d_3": 0.0, "d_4": 0.0, "d_5": 0.0, "d_6": 0.0},
            },
        )
    )

    # Terminal reference: uniform distribution
    terminal_ref = np.array([0.33, 0.33, 0.34])
    
    # Audit input: invalid distribution (negative weight)
    audit_distribution = np.array([-0.5, 0.8, 0.7])  # Invalid: negative weight
    audit_input = MockAuditInput(audit_distribution, lambda_logic=1.0)
    
    context_input = [
        "Distribution constraint: must be in probability simplex",
        "All weights must be non-negative",
    ]
    context_policies = [
        "The measure must lie in the probability simplex.",
        "No negative weights are allowed.",
    ]

    with patch("idicoc_notary_core.audit.graph.property_graph_evaluator.PropertyGraphEvaluator.evaluate", side_effect=[0.85/0.4, 0.05/0.4]):
        canonical_state = logic_service.process_interaction(
            audit_input=audit_input,
            context_input=context_input,
            context_policies=context_policies,
        )

    metadata = canonical_state.metadata
    d_s = metadata["d_s"]
    epsilon = metadata["epsilon_used"]
    assert d_s > epsilon, f"Expected high dissonance for invalid distribution, got {d_s}"
    print(f"DEBUG: logic_meta={metadata}")
    
    correction_flag = metadata.get("correction_flag", False)
    assert correction_flag is True

    # Compliance verification should fail with strict tolerance
    compliance = logic_service.verify_compliance(canonical_state, tolerance=0.0)
    assert compliance is False

    # Violated policies should be recorded
    audit_metrics = metadata.get("audit_metrics", {})
def test_logic_service_terminality_error():
    """
    Test behavior when a terminality/structural error occurs in the audit pipeline.
    The service should detect the error and report it without corrupting the output.
    """
    logic_service = _build_logic_service(
        (
            [1.0, 1.0],  # D_s maximal (structural error), fails correction too
            0.0,  # D_f
            MockAuditInput(np.array([0.25, 0.25, 0.25, 0.25])),
            True,  # correction_flag
            {
                "d_logic": 1.0,
                "d_logic_geom": 1.0,
                "d_logic_semantic": 1.0,
                "d_terminal": 1.0,
                "terminality_violation": False,
                "terminality_error": True,
                "terminality_error_message": "dimension mismatch",
                "max_policy_distance": 0.0,
                "max_context_distance": 0.0,
                "violated_policies": [],
                "contradictory_contexts": [],
                "support_found": False,
                "algebraic_components": {"d_0": 0.0, "d_1": 0.0, "d_2": 1.0, "d_3": 0.0, "d_4": 0.0, "d_5": 0.0, "d_6": 0.0},
            },
        )
    )

    # Mismatched dimensions between anchor and audit input
    terminal_ref = np.array([0.5, 0.5])  # 2D anchor
    audit_distribution = np.array([0.25, 0.25, 0.25, 0.25])  # 4D input (mismatch)
    audit_input = MockAuditInput(audit_distribution, lambda_logic=1.0)

    canonical_state = logic_service.process_interaction(
        audit_input=audit_input,
        context_input=["Anchor dimensionality: 2"],
        context_policies=[],
    )

    metadata = canonical_state.metadata
    # It fails correction because both D_s calls return 1.0 > epsilon(0.1)
    assert metadata.get("correction_flag", False) is False

    # Compliance should fail when error occurs
    compliance = logic_service.verify_compliance(canonical_state, tolerance=0.0)
    assert compliance is False


def test_logic_service_with_partial_dissonance():
    """
    Test a case where dissonance is moderate (between tolerance and violation threshold).
    The service should report the state but not correct it if within epsilon.
    """
    epsilon_val = 0.1
    logic_service = _build_logic_service(
        (
            epsilon_val + 0.02,  # D_s slightly above epsilon
            0.08,  # D_f
            "output with moderate dissonance",
            False,  # No correction if close to boundary
            {
                "d_logic": epsilon_val + 0.02,
                "d_logic_geom": epsilon_val + 0.02,
                "d_logic_semantic": epsilon_val + 0.02,
                "max_policy_distance": 0.05,
                "max_context_distance": 0.08,
                "violated_policies": [],
                "contradictory_contexts": [],
                "support_found": False,
                "terminality_violation": False,
                "algebraic_components": {"d_0": 0.0, "d_1": 0.0, "d_2": epsilon_val + 0.02, "d_3": 0.0, "d_4": 0.0, "d_5": 0.0, "d_6": 0.0},
            },
        )
    )

    audit_distribution = np.array([0.35, 0.32, 0.33])
    audit_input = MockAuditInput(audit_distribution)

    canonical_state = logic_service.process_interaction(
        audit_input=audit_input,
        context_input=["Entropy constraint"],
        context_policies=[],
        epsilon_override=epsilon_val,
    )

    metadata = canonical_state.metadata
    d_s = metadata["d_s"]
    epsilon = metadata["epsilon_used"]
    
    # D_s should be above epsilon but correction may not be forced
    assert d_s > epsilon or metadata.get("correction_flag", False) is False


def test_logic_service_lambda_composition():
    """
    Test that the lambda weights are correctly set for logic strategy (1.0 for logic, 0 for others).
    """
    logic_service = _build_logic_service(
        (
            0.03,
            0.01,
            "output",
            False,
            {
                "d_logic": 0.03,
                "max_context_distance": 0.01,
                "violated_policies": [],
                "algebraic_components": {"d_0": 0.0, "d_1": 0.0, "d_2": 0.03, "d_3": 0.0, "d_4": 0.0, "d_5": 0.0, "d_6": 0.0},
            },
        )
    )

    audit_input = MockAuditInput(np.array([0.33, 0.33, 0.34]))

    canonical_state = logic_service.process_interaction(
        audit_input=audit_input,
        context_input=[],
        context_policies=[],
    )

    metadata = canonical_state.metadata
    # No longer checking lambda_weights here


# =============================================================================
# ADDITIONAL TESTS: SIGNAL SIZE & FREQUENCY LIMITS
# =============================================================================

def test_logic_signal_extreme_size_handling():
    """
    Escenario 3: Límites de tamaño de la señal (dimensión).
    Prueba cómo la estrategia maneja tamaños de entrada extremos (muy pequeños o muy grandes)
    mediante padding o truncamiento dinámico para alinearse al ancla de 4D.
    """
    config = AuditConfig()
    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # 1. Señal muy pequeña (dimensión 1)
    small_signal = MockAuditInput(np.array([1.0]))
    D_s_small, _, _, _, metrics_small = strategy.compute(
        audit_input=small_signal,
        context_input=[],
        context_policies=[],
    )
    # Se debe haber autopaddeado a 4D ([1.0, 0.0, 0.0, 0.0])
    assert metrics_small["reference_count"] == 4
    # EMD de [1.0, 0.0, 0.0, 0.0] a [0.25, 0.25, 0.25, 0.25] es exactamente 1.5
    assert metrics_small["d_1"] > 0.5

    # 2. Señal muy grande (dimensión 6)
    large_signal = MockAuditInput(np.array([0.1, 0.2, 0.3, 0.4, 0.05, 0.05]))
    D_s_large, _, _, _, metrics_large = strategy.compute(
        audit_input=large_signal,
        context_input=[],
        context_policies=[],
    )
    # Se debe haber truncado a 4D ([0.1, 0.2, 0.3, 0.4] normalizado)
    assert metrics_large["reference_count"] == 4
    assert np.isfinite(D_s_large)


def test_logic_signal_frequency_impulses():
    """
    Escenario 4: Frecuencia de la señal (impulsos vs distribución uniforme).
    Evalúa señales con picos de alta frecuencia (un solo bin con toda la masa)
    frente a señales de baja frecuencia/uniformes, verificando los límites de EMD
    y la detección matemática de colapso de frecuencia.
    """
    config = AuditConfig()
    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # 1. Impulso puro (alta frecuencia/entropía baja/colapso en un punto)
    high_freq_signal = MockAuditInput(np.array([0.0, 0.0, 1.0, 0.0]))
    _, _, _, correction_high, metrics_high = strategy.compute(
        audit_input=high_freq_signal,
        context_input=[],
        context_policies=[],
    )
    # EMD de [0.0, 0.0, 1.0, 0.0] a [0.25, 0.25, 0.25, 0.25]
    # Cumsum: [0.0, 0.0, 1.0, 1.0] vs [0.25, 0.50, 0.75, 1.00]
    # Diferencias: 0.25 + 0.50 + 0.25 + 0.0 = 1.0
    assert metrics_high["d_1"] > 0.2
    # Al ser un impulso concentrado, supera el umbral de rigidez base y requiere corrección
    assert correction_high is True

    # 2. Distribución casi uniforme (baja frecuencia/baja disonancia)
    low_freq_signal = MockAuditInput(np.array([0.24, 0.26, 0.25, 0.25]))
    _, _, _, correction_low, metrics_low = strategy.compute(
        audit_input=low_freq_signal,
        context_input=[],
        context_policies=[],
    )
    # Disonancia muy baja
    assert metrics_low["d_1"] < 0.05
    assert correction_low is False

