"""
Test suite for LogicDissonanceStrategy: Mathematical validation of Kantorovich EMD
and irrefutable terminality judgment through optimal transport.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock

from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.dse import LogicDissonanceStrategy


class MockAuditInput:
    """Mock input that simulates a measure (distribution) in the probability simplex."""
    def __init__(self, distribution: np.ndarray, lambda_logic: float = 1.0):
        self.distribution = distribution
        self.lambda_logic = lambda_logic


# =============================================================================
# TEST 1: Identity Invariance — Zero Dissonance for Identical Distributions
# =============================================================================
def test_logic_strategy_identity_invariance():
    """
    Test 1: Introduce a vector identical to the SourceAnchor.
    d_logic must be 0.0 (zero dissonance for identical distributions).
    
    This validates that the EMD calculation is mathematically correct and 
    free of entropy leaks in normalization.
    """
    # Terminal reference: uniform distribution over 3 elements
    terminal_ref = np.array([0.33, 0.33, 0.34])
    
    config = AuditConfig()
    config.constant_k = terminal_ref
    config.isg_delta_fp = 0.15
    
    strategy = LogicDissonanceStrategy(config)
    
    # Input identical to the terminal reference
    audit_input = MockAuditInput(terminal_ref, lambda_logic=1.0)
    
    D_s, D_f, corrected_output, correction_flag, metrics = strategy.compute(
        audit_input=audit_input,
        context_input=[],
        context_axioms=[],
        epsilon=0.0,
        validate_conflicts=False,
    )
    
    # Assertions: d_logic must be 0.0 (or extremely close due to float precision)
    assert metrics["d_logic"] < 1e-10, (
        f"Identity invariance violated: d_logic={metrics['d_logic']}, "
        "expected ≈0.0 for identical distributions"
    )
    assert D_s < 1e-10, (
        f"D_s should be ~0.0 for identical input and anchor, got {D_s}"
    )
    assert correction_flag is False, (
        f"correction_flag should be False when d_s ≈ 0.0, got {correction_flag}"
    )
    assert metrics["terminality_violation"] is False


# =============================================================================
# TEST 2: Orthogonal Maximum — Maximum Dissonance for Opposite Distributions
# =============================================================================
def test_logic_strategy_orthogonal_maximum():
    """
    Test 2: Introduce a vector orthogonal to the SourceAnchor (Dirac delta).
    d_logic should be maximum (approaching 2.0 for 1-Wasserstein distance).
    
    This validates that the strategy correctly identifies maximally divergent
    distributions and triggers the correction flag.
    """
    # Terminal reference: uniform distribution
    terminal_ref = np.array([0.25, 0.25, 0.25, 0.25])
    
    config = AuditConfig()
    config.constant_k = terminal_ref
    config.isg_delta_fp = 0.05  # Very strict tolerance
    
    strategy = LogicDissonanceStrategy(config)
    
    # Orthogonal (Dirac delta): all mass at first element
    dirac_delta = np.array([1.0, 0.0, 0.0, 0.0])
    audit_input = MockAuditInput(dirac_delta, lambda_logic=1.0)
    
    D_s, D_f, corrected_output, correction_flag, metrics = strategy.compute(
        audit_input=audit_input,
        context_input=[],
        context_axioms=[],
        epsilon=0.0,
        validate_conflicts=False,
    )
    
    # For 1-Wasserstein distance between uniform and delta:
    # distance = sum of absolute differences in CDFs
    # Expected d_logic ≈ 0.75 (area under the curve difference)
    assert metrics["d_logic"] > 0.5, (
        f"Orthogonal case should produce high d_logic, got {metrics['d_logic']}"
    )
    assert correction_flag is True, (
        f"correction_flag should be True for high dissonance, got {correction_flag}"
    )
    assert metrics["terminality_violation"] is True


# =============================================================================
# TEST 3: Correction Flag Threshold — Automatic Activation at delta_fp Boundary
# =============================================================================
def test_logic_strategy_correction_flag_threshold():
    """
    Test 3: Verify that correction_flag activates when d_s > delta_fp.
    
    This validates the "Axiom of Rigidity": the admissible manifold is
    precisely defined as D_s <= delta_fp + epsilon, and correction occurs
    when this boundary is crossed.
    """
    terminal_ref = np.array([0.5, 0.5])
    
    config = AuditConfig()
    config.constant_k = terminal_ref
    delta_fp = 0.2  # Strict but not extreme
    config.isg_delta_fp = delta_fp
    
    strategy = LogicDissonanceStrategy(config, delta_fp=delta_fp)
    
    # Case 1: Distribution just below threshold (should comply)
    # Distribution: [0.6, 0.4] vs anchor [0.5, 0.5]
    # Cumsum: [0.6, 1.0] vs [0.5, 1.0]
    # 1-Wasserstein: |0.6 - 0.5| + |1.0 - 1.0| = 0.1
    compliant_input = MockAuditInput(np.array([0.6, 0.4]), lambda_logic=1.0)
    D_s_compliant, _, _, flag_compliant, metrics_compliant = strategy.compute(
        audit_input=compliant_input,
        context_input=[],
        context_axioms=[],
        epsilon=0.0,
    )
    
    assert D_s_compliant <= delta_fp, (
        f"Compliant case should have d_s <= {delta_fp}, got {D_s_compliant}"
    )
    assert flag_compliant is False, (
        f"correction_flag should be False when within threshold, got {flag_compliant}"
    )
    
    # Case 2: Distribution beyond threshold (should trigger correction)
    # Distribution: [0.75, 0.25] vs anchor [0.5, 0.5]
    # Cumsum: [0.75, 1.0] vs [0.5, 1.0]
    # 1-Wasserstein: |0.75 - 0.5| + |1.0 - 1.0| = 0.25
    non_compliant_input = MockAuditInput(np.array([0.75, 0.25]), lambda_logic=1.0)
    D_s_non_compliant, _, _, flag_non_compliant, metrics_non_compliant = strategy.compute(
        audit_input=non_compliant_input,
        context_input=[],
        context_axioms=[],
        epsilon=0.0,
    )
    
    assert D_s_non_compliant > delta_fp, (
        f"Non-compliant case should have d_s > {delta_fp}, got {D_s_non_compliant}"
    )
    assert flag_non_compliant is True, (
        f"correction_flag should be True when exceeding threshold, got {flag_non_compliant}"
    )


# =============================================================================
# TEST 4: Epsilon Dynamic Adjustment — Manifold Expansion
# =============================================================================
def test_logic_strategy_epsilon_adjustment():
    """
    Test 4: Verify that epsilon extends the admissible manifold dynamically.
    
    With epsilon > 0, the effective threshold becomes delta_fp + epsilon,
    allowing inputs that would otherwise trigger correction.
    """
    terminal_ref = np.array([0.5, 0.5])
    
    config = AuditConfig()
    config.constant_k = terminal_ref
    delta_fp = 0.1
    config.isg_delta_fp = delta_fp
    
    strategy = LogicDissonanceStrategy(config, delta_fp=delta_fp)
    
    # Borderline input: d_logic ≈ 0.15 (exceeds delta_fp=0.1)
    borderline_input = MockAuditInput(np.array([0.65, 0.35]), lambda_logic=1.0)
    
    # Without epsilon: should trigger correction
    D_s_strict, _, _, flag_strict, _ = strategy.compute(
        audit_input=borderline_input,
        context_input=[],
        context_axioms=[],
        epsilon=0.0,
    )
    assert flag_strict is True, "Expected correction without epsilon"
    
    # With sufficient epsilon: should be compliant
    # d_logic ≈ 0.15, effective_threshold = 0.1 + 0.1 = 0.2
    D_s_relaxed, _, _, flag_relaxed, metrics_relaxed = strategy.compute(
        audit_input=borderline_input,
        context_input=[],
        context_axioms=[],
        epsilon=0.1,  # Relaxes the manifold
    )
    assert flag_relaxed is False, (
        f"With epsilon=0.1, correction_flag should be False, got {flag_relaxed}. "
        f"D_s={D_s_relaxed}, effective_threshold={metrics_relaxed['effective_threshold']}"
    )


# =============================================================================
# TEST 5: Lambda Logic Scaling — Proportional Dissonance Amplification
# =============================================================================
def test_logic_strategy_lambda_logic_scaling():
    """
    Test 5: Verify that lambda_logic proportionally scales d_s.
    
    The dissonance is: D_s = lambda_logic * d_logic
    Doubling lambda_logic should double D_s while keeping d_logic constant.
    """
    terminal_ref = np.array([0.5, 0.5])
    
    config = AuditConfig()
    config.constant_k = terminal_ref
    config.isg_delta_fp = 0.5  # Allow high values for this test
    
    strategy = LogicDissonanceStrategy(config)
    
    # Same measure, different lambda_logic values
    measure = np.array([0.6, 0.4])
    
    input_lambda_1 = MockAuditInput(measure, lambda_logic=1.0)
    D_s_1, _, _, _, metrics_1 = strategy.compute(
        audit_input=input_lambda_1,
        context_input=[],
        context_axioms=[],
        epsilon=0.0,
    )
    
    input_lambda_2 = MockAuditInput(measure, lambda_logic=2.0)
    D_s_2, _, _, _, metrics_2 = strategy.compute(
        audit_input=input_lambda_2,
        context_input=[],
        context_axioms=[],
        epsilon=0.0,
    )
    
    # d_logic should remain the same
    assert abs(metrics_1["d_logic"] - metrics_2["d_logic"]) < 1e-10, (
        "d_logic should be independent of lambda_logic"
    )
    
    # D_s should scale proportionally
    assert abs(D_s_2 - 2 * D_s_1) < 1e-10, (
        f"D_s should scale with lambda_logic: 2*D_s_1={2*D_s_1}, D_s_2={D_s_2}"
    )


# =============================================================================
# TEST 6: Numerical Stability — Floating Point Robustness
# =============================================================================
def test_logic_strategy_numerical_stability():
    """
    Test 6: Verify numerical stability with very small and very large distributions.
    
    The strategy should handle edge cases gracefully without NaN or Inf.
    """
    terminal_ref = np.array([1e-10, 1.0 - 1e-10])
    
    config = AuditConfig()
    config.constant_k = terminal_ref
    config.isg_delta_fp = 0.5
    
    strategy = LogicDissonanceStrategy(config)
    
    # Tiny distribution (extreme probability mass at second element)
    tiny_input = MockAuditInput(np.array([1e-12, 1.0 - 1e-12]), lambda_logic=1.0)
    D_s, _, _, correction_flag, metrics = strategy.compute(
        audit_input=tiny_input,
        context_input=[],
        context_axioms=[],
        epsilon=0.0,
    )
    
    # Check for NaN, Inf, or invalid values
    assert np.isfinite(D_s), f"D_s should be finite, got {D_s}"
    assert np.isfinite(metrics["d_logic"]), f"d_logic should be finite, got {metrics['d_logic']}"
    assert isinstance(correction_flag, bool), f"correction_flag should be bool, got {type(correction_flag)}"
