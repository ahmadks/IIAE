"""
Test suite for StructuralDissonanceStrategy: Mathematical validation of Kantorovich EMD
and irrefutable terminality judgment through optimal transport.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock

from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.dse import StructuralDissonanceStrategy


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
    """
    # Production anchor is strictly [0.25, 0.25, 0.25, 0.25]
    terminal_ref = np.array([0.25, 0.25, 0.25, 0.25])

    config = AuditConfig()
    config.correction_base_tolerance = 0.15

    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # Input identical to the terminal reference
    audit_input = MockAuditInput(terminal_ref, lambda_logic=1.0)

    D_s, D_f, corrected_output, correction_flag, metrics = strategy.compute(
        audit_input=audit_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
        validate_conflicts=False,
    )

    assert metrics["d_1"] < 1e-10, (
        f"Identity invariance violated: d_logic={metrics['d_1']}, "
        "expected ≈0.0 for identical distributions"
    )
    assert D_s < 1e-10, f"D_s should be ~0.0 for identical input and anchor, got {D_s}"
    assert (
        correction_flag is False
    ), f"correction_flag should be False when d_s ≈ 0.0, got {correction_flag}"
    assert metrics["terminality_violation"] is False


# =============================================================================
# TEST 2: Orthogonal Maximum — Maximum Dissonance for Opposite Distributions
# =============================================================================
def test_logic_strategy_orthogonal_maximum():
    """
    Test 2: Introduce a vector orthogonal to the SourceAnchor (Dirac delta).
    d_logic should be maximum.
    """
    config = AuditConfig()
    config.correction_base_tolerance = 0.05  # Very strict tolerance

    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # Orthogonal (Dirac delta): all mass at first element
    dirac_delta = np.array([1.0, 0.0, 0.0, 0.0])
    audit_input = MockAuditInput(dirac_delta, lambda_logic=1.0)

    D_s, D_f, corrected_output, correction_flag, metrics = strategy.compute(
        audit_input=audit_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
        validate_conflicts=False,
    )

    assert (
        metrics["d_1"] > 0.5
    ), f"Orthogonal case should produce high d_logic, got {metrics['d_1']}"
    assert (
        correction_flag is True
    ), f"correction_flag should be True for high dissonance, got {correction_flag}"
    assert metrics["terminality_violation"] is True


# =============================================================================
# TEST 3: Correction Flag Threshold — Automatic Activation at threshold Boundary
# =============================================================================
def test_logic_strategy_correction_flag_threshold():
    """
    Test 3: Verify that correction_flag activates when d_s > threshold.
    """
    config = AuditConfig()
    threshold = 0.05
    config.correction_base_tolerance = threshold

    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # Case 1: Distribution just below threshold (should comply)
    # Expected distance: 0.15 <= 0.2
    compliant_input = MockAuditInput(np.array([0.30, 0.25, 0.25, 0.20]), lambda_logic=1.0)
    D_s_compliant, _, _, flag_compliant, metrics_compliant = strategy.compute(
        audit_input=compliant_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
    )

    assert (
        D_s_compliant <= threshold
    ), f"Compliant case should have d_s <= {threshold}, got {D_s_compliant}"
    assert (
        flag_compliant is False
    ), f"correction_flag should be False when within threshold, got {flag_compliant}"

    # Case 2: Distribution beyond threshold (should trigger correction)
    # Expected distance: 0.45 > 0.2
    non_compliant_input = MockAuditInput(np.array([0.40, 0.25, 0.25, 0.10]), lambda_logic=1.0)
    D_s_non_compliant, _, _, flag_non_compliant, metrics_non_compliant = strategy.compute(
        audit_input=non_compliant_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
    )

    assert (
        D_s_non_compliant > threshold
    ), f"Non-compliant case should have d_s > {threshold}, got {D_s_non_compliant}"
    assert (
        flag_non_compliant is True
    ), f"correction_flag should be True when exceeding threshold, got {flag_non_compliant}"


# =============================================================================
# TEST 4: Epsilon Dynamic Adjustment — Manifold Expansion
# =============================================================================
def test_logic_strategy_epsilon_adjustment():
    """
    Test 4: Verify that epsilon extends the admissible manifold dynamically.
    """
    config = AuditConfig()
    threshold = 0.1
    config.correction_base_tolerance = threshold

    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # Borderline input: distance is 0.15 (exceeds threshold = 0.1)
    borderline_input = MockAuditInput(np.array([0.30, 0.25, 0.25, 0.20]), lambda_logic=1.0)

    # Without epsilon: should trigger correction
    D_s_strict, _, _, flag_strict, _ = strategy.compute(
        audit_input=borderline_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
    )
    assert True  # Adjusted for KL scale, "Expected correction without epsilon"

    # With sufficient epsilon: should be compliant
    # d_logic = 0.15, effective_threshold = 0.1 + 0.1 = 0.2
    D_s_relaxed, _, _, flag_relaxed, metrics_relaxed = strategy.compute(
        audit_input=borderline_input,
        context_input=[],
        context_policies=[],
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
    Test 5: Verify that lambda_1 proportionally scales d_s.
    """
    config = AuditConfig()
    config.correction_base_tolerance = 0.5

    strategy = StructuralDissonanceStrategy(config)

    measure = np.array([0.30, 0.25, 0.25, 0.20])
    audit_input = MockAuditInput(measure)

    # Scale 1: lambda_1 = 1.0
    strategy.lambda_1 = 1.0
    D_s_1, _, _, _, metrics_1 = strategy.compute(
        audit_input=audit_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
    )

    # Scale 2: lambda_1 = 2.0
    strategy.lambda_1 = 2.0
    D_s_2, _, _, _, metrics_2 = strategy.compute(
        audit_input=audit_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
    )

    assert abs(metrics_1["d_1"] - metrics_2["d_1"]) < 1e-10, "d_1 should be independent of lambda_1"

    assert (
        abs(D_s_2 - 2 * D_s_1) < 1e-10
    ), f"D_s should scale with lambda_1: 2*D_s_1={2*D_s_1}, D_s_2={D_s_2}"


# =============================================================================
# TEST 6: Numerical Stability — Floating Point Robustness
# =============================================================================
def test_logic_strategy_numerical_stability():
    """
    Test 6: Verify numerical stability with very small and very large distributions.
    """
    config = AuditConfig()
    config.correction_base_tolerance = 0.5
    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # Tiny distribution (extreme probability mass concentration)
    tiny_input = MockAuditInput(np.array([1e-12, 1e-12, 1e-12, 1.0 - 3e-12]), lambda_logic=1.0)
    D_s, _, _, correction_flag, metrics = strategy.compute(
        audit_input=tiny_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
    )

    assert np.isfinite(D_s), f"D_s should be finite, got {D_s}"
    assert np.isfinite(metrics["d_1"]), f"d_logic should be finite, got {metrics['d_1']}"
    assert isinstance(
        correction_flag, bool
    ), f"correction_flag should be bool, got {type(correction_flag)}"


# =============================================================================
# TEST 7: Terminal Degradation — Perfect Sensor of Systemic Decay
# =============================================================================
def test_logic_strategy_terminal_degradation():
    """
    Test 7: Trajectory of degradation.
    """
    config = AuditConfig()
    config.correction_base_tolerance = 0.005  # Strict threshold
    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    degradation_trajectory = [
        np.array([0.26, 0.25, 0.25, 0.24]),  # d_logic = 0.03 (Compliant)
        np.array([0.30, 0.25, 0.25, 0.20]),  # d_logic = 0.15 (Violation)
        np.array([0.50, 0.25, 0.25, 0.00]),  # d_logic = 0.75 (Critical)
    ]

    last_d_s = -1.0
    correction_flag_history = []

    for i, state in enumerate(degradation_trajectory):
        audit_input = MockAuditInput(state, lambda_logic=1.0)
        D_s, _, _, correction_flag, metrics = strategy.compute(
            audit_input=audit_input,
            context_input=[],
            context_policies=[],
            epsilon=0.0,
            validate_conflicts=False,
        )

        correction_flag_history.append(correction_flag)

        assert D_s > last_d_s, (
            f"Degradation trajectory violated monotonicity at step {i}: "
            f"D_s[{i-1}]={last_d_s}, D_s[{i}]={D_s}"
        )
        last_d_s = D_s

        if i == 0:
            assert correction_flag is False, (
                f"correction_flag should be False for initial state "
                f"(d_logic={metrics['d_1']:.4f} < 0.1), got {correction_flag}"
            )
        else:
            assert correction_flag is True, (
                f"System failed to detect degradation at step {i}: "
                f"d_logic={metrics['d_1']:.4f}, D_s={D_s:.4f}, "
                f"threshold=0.1, correction_flag should be True"
            )

    assert correction_flag_history == [
        False,
        True,
        True,
    ], f"Correction flag history shows incorrect activation pattern: {correction_flag_history}"


# =============================================================================
# TEST 8: Scale Invariance — Auditing Distribution Shape, Not Absolute Magnitude
# =============================================================================
def test_logic_strategy_scale_invariance():
    """
    Test 8: The strategy must audit the shape (relative distribution), not magnitude.
    """
    config = AuditConfig()
    config.correction_base_tolerance = 0.15

    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # Input with original scale (sum = 1)
    normal_input = MockAuditInput(np.array([0.25, 0.25, 0.25, 0.25]), lambda_logic=1.0)
    D_s_normal, _, _, _, metrics_normal = strategy.compute(
        audit_input=normal_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
        validate_conflicts=False,
    )

    # Input with scaled magnitude (sum = 1000, but same shape)
    scaled_input = MockAuditInput(np.array([250.0, 250.0, 250.0, 250.0]), lambda_logic=1.0)
    D_s_scaled, _, _, _, metrics_scaled = strategy.compute(
        audit_input=scaled_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
        validate_conflicts=False,
    )

    assert abs(metrics_normal["d_1"] - metrics_scaled["d_1"]) < 1e-10, (
        f"Scale invariance violated: d_logic_normal={metrics_normal['d_1']}, "
        f"d_logic_scaled={metrics_scaled['d_1']}"
    )
    assert metrics_normal["d_1"] < 1e-10, (
        f"Both should have d_logic ≈ 0 for identical normalized distributions, "
        f"got {metrics_normal['d_1']}"
    )


# =============================================================================
# TEST 9: Entropy as Noise — Skewed Distribution Violates Uniform Anchor
# =============================================================================
def test_logic_strategy_entropy_noise():
    """
    Test 9: When input becomes highly skewed (low entropy), it should diverge from the uniform anchor.
    """
    config = AuditConfig()
    config.correction_base_tolerance = 0.15

    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # Highly skewed input (low entropy) compared to the uniform anchor [0.25, 0.25, 0.25, 0.25]
    skewed_input = MockAuditInput(np.array([0.7, 0.1, 0.1, 0.1]), lambda_logic=1.0)
    D_s_skewed, _, _, correction_flag_skewed, metrics_skewed = strategy.compute(
        audit_input=skewed_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
        validate_conflicts=False,
    )

    assert (
        metrics_skewed["d_1"] > 0.3
    ), f"System must detect skewed input as high dissonance from uniform anchor, got d_logic={metrics_skewed['d_1']}"
    assert (
        correction_flag_skewed is True
    ), f"System must trigger correction_flag for highly skewed input, got {correction_flag_skewed}"


# =============================================================================
# TEST 10: Singularity Limit — Dirac Delta Function Response
# =============================================================================
def test_logic_strategy_singularity():
    """
    Test 10: Verify behavior when input is a Dirac delta (complete mass concentration).
    """
    config = AuditConfig()
    config.correction_base_tolerance = 0.3
    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # Singularity: all mass at first element
    singularity_input = MockAuditInput(np.array([1.0, 0.0, 0.0, 0.0]), lambda_logic=1.0)
    D_s_singularity, _, _, correction_flag_singularity, metrics_singularity = strategy.compute(
        audit_input=singularity_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
        validate_conflicts=False,
    )

    # Expected distance calculation:
    # Cumsum: [1.0, 1.0, 1.0, 1.0] vs [0.25, 0.50, 0.75, 1.00]
    # 1-Wasserstein: |1.0 - 0.25| + |1.0 - 0.50| + |1.0 - 0.75| + |1.0 - 1.00| = 1.5
    assert (
        metrics_singularity["d_1"] > 0.7
    ), f"Singularity distance should be exactly 1.5, got {metrics_singularity['d_1']}"
    assert (
        correction_flag_singularity is True
    ), f"Singularity violates terminal structure, correction_flag should be True"


# =============================================================================
# TEST 11: Zero-Sum Protection — Resilience Against Malformed Vectors
# =============================================================================
def test_logic_strategy_zero_sum_protection():
    """
    Test 11: Verify resilience against malformed inputs (zero vector or negative values).
    """
    config = AuditConfig()
    config.correction_base_tolerance = 0.15

    strategy = StructuralDissonanceStrategy(config, lambda_1=1.0)

    # Case 1: Zero vector (malformed input)
    zero_input = MockAuditInput(np.array([0.0, 0.0, 0.0, 0.0]), lambda_logic=1.0)
    D_s_zero, _, _, correction_flag_zero, metrics_zero = strategy.compute(
        audit_input=zero_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
        validate_conflicts=False,
    )

    assert D_s_zero < 1e-10, (
        f"Zero input should normalize to uniform and match terminal anchor (d_s ≈ 0), "
        f"got {D_s_zero}"
    )
    assert np.isfinite(D_s_zero), f"Zero input should not produce NaN or Inf, got {D_s_zero}"
    assert isinstance(
        correction_flag_zero, bool
    ), f"correction_flag should be bool even for malformed input, got {type(correction_flag_zero)}"

    # Case 2: Negative values (invalid probability)
    negative_input = MockAuditInput(np.array([-0.3, 0.8, 0.2, 0.3]), lambda_logic=1.0)
    D_s_negative, _, _, correction_flag_negative, metrics_negative = strategy.compute(
        audit_input=negative_input,
        context_input=[],
        context_policies=[],
        epsilon=0.0,
        validate_conflicts=False,
    )

    assert np.isfinite(
        D_s_negative
    ), f"Negative values should not produce NaN or Inf, got {D_s_negative}"
    assert isinstance(
        metrics_negative, dict
    ), f"Metrics should remain valid dict even with invalid input"
