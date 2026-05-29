import pytest
import warnings
import numpy as np
import torch
from unittest.mock import MagicMock, patch

from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.base import CanonicalStateDTO
from idicoc_notary_core.audit.pipeline import IDICOCPipeline
from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient
from idicoc_notary_core.kernel.projection.invariant_state_generator import (
    InvariantStateGenerator,
    CanonicalState,
)
from idicoc_notary_core.kernel.source.anchor import SourceAnchor
from idicoc_notary_core.kernel.verification.registry import ProjectionRegistry


# ===================================================================
# TEST 1: Config class validation and property checks
# ===================================================================
def test_audit_config_properties():
    # Instantiating with default values
    config = AuditConfig()
    assert config.correction_base_tolerance == 0.15
    assert config.instance_name == "ai_comercial"
    assert not hasattr(config, "mode")
    assert config.enable_hard_halt is False

    # Check warning when enable_hard_halt is set to True
    with pytest.warns(UserWarning, match="enable_hard_halt ha sido forzada a False"):
        config_warn = AuditConfig(enable_hard_halt=True)
    assert config_warn.enable_hard_halt is False


# ===================================================================
# TEST 2: InvariantStateGenerator preserves signal magnitude
# ===================================================================
def test_invariant_state_generator_preserves_text_signal():
    anchor = SourceAnchor()
    registry = ProjectionRegistry()
    isg = InvariantStateGenerator(anchor, registry)

    state = isg.generate("test_anchor text")
    assert isinstance(state.measure_vector, np.ndarray)
    assert state.measure_vector.size > 0


def test_invariant_state_generator_preserves_exact_vector_input():
    anchor = SourceAnchor()
    registry = ProjectionRegistry()
    isg = InvariantStateGenerator(anchor, registry)

    state = isg.generate(np.array([1.0, 0.0, 0.0, 0.0], dtype=float))
    assert isinstance(state.measure_vector, np.ndarray)
    assert np.array_equal(state.measure_vector, np.array([1.0, 0.0, 0.0, 0.0], dtype=float))


# ===================================================================
# TEST 7: algebraic_components present and correct in pipeline metadata
# ===================================================================
def test_pipeline_algebraic_components_in_metadata():
    mock_strategy_instance = MagicMock()
    mock_strategy_instance.compute_dissonance.return_value = 0.3
    mock_strategy_instance.lambda_weights = [0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0]
    mock_strategy_instance._d_inv_from_pair = MagicMock(return_value=0.0)

    mock_strategy_class = MagicMock(return_value=mock_strategy_instance)
    # Patch the config to return the right expected weights in the pipeline
    mock_strategy_class.lambda_weights = [0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0]

    config = AuditConfig(
        dissonance_strategy=mock_strategy_class,
        dissonance_weights=(0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0),
    )
    wrapper = IDICOCNotaryClient(config)

    state = wrapper.process_interaction(
        audit_input="test input",
        context_input=["ctx"],
        context_policies=["ax"],
    )

    assert isinstance(state, CanonicalStateDTO)
    ac = state.metadata.get("algebraic_components")
    assert ac is not None, "algebraic_components debe estar en el metadata del estado canónico"
    assert "lambda_weights" not in ac
    assert ac["d_1"] == 0.0
    assert ac["d_3"] == 0.0
    assert "d_2" in ac


# ===================================================================
# TEST 8: verify_compliance validates coalgebraic weights and D_s=d_logic
# ===================================================================
def test_verify_compliance_algebraic_validation():
    # Stub the strategy so no ML models are loaded
    mock_strategy_instance = MagicMock()
    mock_strategy_instance.lambda_weights = [0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0]
    mock_strategy_instance._d_inv_from_pair = MagicMock(return_value=0.0)
    mock_strategy_class = MagicMock(return_value=mock_strategy_instance)
    # Patch the class so the wrapper pipeline correctly reads expected_weights
    mock_strategy_class.lambda_weights = [0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0]

    config = AuditConfig(
        rigidity_epsilon=1.0,
        dissonance_strategy=mock_strategy_class,
        dissonance_weights=(0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0),
    )
    wrapper = IDICOCNotaryClient(config)

    # Case 1: valid algebraic components → should return True
    valid_state = CanonicalStateDTO(
        data="output",
        metadata={
            "d_s": 0.12,  # 0.5*0 + 0.4*0.3 + 0.1*0 = 0.12
            "algebraic_components": {
                "d_0": 0.0,
                "d_1": 0.0,
                "d_2": 0.3,
                "d_3": 0.0,
                "d_4": 0.0,
                "d_5": 0.0,
                "d_6": 0.0,
            },
        },
    )
    assert wrapper.verify_compliance(valid_state) is True

    # Case 2: d_s does not match expected_d_s → should return False
    mismatched_state = CanonicalStateDTO(
        data="output",
        metadata={
            "d_s": 0.5,  # does not match d_logic=0.3
            "algebraic_components": {
                "d_0": 0.0,
                "d_1": 0.0,
                "d_2": 0.3,
                "d_3": 0.0,
                "d_4": 0.0,
                "d_5": 0.0,
                "d_6": 0.0,
            },
        },
    )
    assert wrapper.verify_compliance(mismatched_state) is False

    # Case 4: missing algebraic_components → should return False
    no_algebraic_state = CanonicalStateDTO(
        data="output",
        metadata={"d_s": 0.1},
    )
    assert wrapper.verify_compliance(no_algebraic_state) is False
