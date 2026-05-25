import pytest
import warnings
import numpy as np
import torch
from unittest.mock import MagicMock, patch

from idicoc_notary_core.audit.config import AuditConfig
from tests.mocks import BankEntropyAnalyzer
from idicoc_notary_core.audit.base import CanonicalStateDTO
from idicoc_notary_core.audit.pipeline import IIAEServiceAuditor
from idicoc_notary_core.audit.wrapper_pipeline import IIAEService
from idicoc_notary_core.kernel.projection.invariant_state_generator import InvariantStateGenerator, CanonicalState
from idicoc_notary_core.kernel.source.anchor import SourceAnchor
from idicoc_notary_core.kernel.verification.registry import ProjectionRegistry


# ===================================================================
# TEST 1: Config class validation and property checks
# ===================================================================
def test_audit_config_properties():
    # Instantiating with default values
    config = AuditConfig()
    assert config.isg_delta_fp == 0.15
    assert config.correction_base_tolerance == 0.15
    assert config.context_axiom_conflict_threshold == 0.5
    assert config.contradiction_snapping_threshold == 0.5
    assert config.source_name == "ai_comercial"
    assert not hasattr(config, "mode")
    assert config.enable_hard_halt is False

    # Check warning when enable_hard_halt is set to True
    with pytest.warns(UserWarning, match="enable_hard_halt ha sido forzada a False"):
        config_warn = AuditConfig(enable_hard_halt=True)
    assert config_warn.enable_hard_halt is False


# ===================================================================
# TEST 2: InvariantStateGenerator with delta_fp
# ===================================================================
def test_invariant_state_generator_delta_fp():
    class DummyAnchor:
        identity = "test_anchor"

    anchor = DummyAnchor()
    registry = ProjectionRegistry()
    
    # ISG with high tolerance delta_fp = 0.99 (collapses to anchor if distance < 0.99)
    # distance for "test_anchor text" vs "test_anchor" is 0.5 < 0.99 -> collapses
    isg_high = InvariantStateGenerator(anchor, registry, delta_fp=0.99)
    state = isg_high.generate("test_anchor text")
    assert state.semantic_vector == "test_anchor"

    # ISG with low tolerance delta_fp = 0.01 (should not collapse)
    # distance for "test_anchor text" vs "test_anchor" is 0.5 >= 0.01 -> does not collapse
    isg_low = InvariantStateGenerator(anchor, registry, delta_fp=0.01)
    state2 = isg_low.generate("test_anchor text")
    assert state2.semantic_vector == "test_anchor text"


# ===================================================================
# TEST 3: Semantic Strategy with mocks
# ===================================================================
@patch('idicoc_notary_core.audit.dse.semantic_strategy.SentenceTransformer')
@patch('idicoc_notary_core.audit.dse.semantic_strategy.AutoTokenizer')
@patch('idicoc_notary_core.audit.dse.semantic_strategy.AutoModelForSequenceClassification')
def test_semantic_strategy_compute(mock_nli_class, mock_tok_class, mock_encoder_class):
    # Set up mocks for sentence transformer and NLI
    mock_encoder = MagicMock()
    mock_encoder_class.return_value = mock_encoder
    
    def mock_encode(text, **kwargs):
        if "support" in text:
            return np.array([1.0, 0.0, 0.0])
        elif "contradict" in text:
            return np.array([0.0, 1.0, 0.0])
        else:
            return np.array([0.5, 0.5, 0.0])
            
    mock_encoder.encode.side_effect = mock_encode

    mock_nli_model = MagicMock()
    mock_nli_class.return_value = mock_nli_model

    config = AuditConfig(
        semantic_embedding_model="mock-embedder",
        semantic_nli_model="mock-nli",
        correction_base_tolerance=0.2,
        contradiction_snapping_threshold=0.6,
        context_axiom_conflict_threshold=0.4,
    )
    
    from idicoc_notary_core.audit.dse import SemanticDissonanceStrategy
    strategy = SemanticDissonanceStrategy(config)
    
    # Patch self._nli_contradiction on strategy
    def mock_nli(premise, hypothesis):
        if "contradict" in premise.lower() or "contradict" in hypothesis.lower():
            return 0.8
        return 0.1
    strategy._nli_contradiction = mock_nli

    # Compute with no disonancia
    strategy._cosine_distance = lambda a, b: 0.05
    D_s, D_f, corrected_output, correction_flag, metrics = strategy.compute(
        audit_input="source text",
        context_input=["support text"],
        context_axioms=["some axiom"],
        epsilon=0.0,
        validate_conflicts=True
    )
    assert correction_flag is False
    assert corrected_output == "source text"
    assert metrics["support_found"] is True
    assert metrics["max_context_distance"] == 0.1
    assert len(metrics["violated_axioms"]) == 0

    # Compute with factual snapping (support_found=False, max_context_distance > snapping_threshold)
    strategy._cosine_distance = lambda a, b: 0.8
    D_s, D_f, corrected_output, correction_flag, metrics = strategy.compute(
        audit_input="source text",
        context_input=["contradict text"],
        context_axioms=["some axiom"],
        epsilon=0.0,
        validate_conflicts=True
    )
    assert correction_flag is True
    assert "[SNAPPING ACTIVE]" in corrected_output
    assert "contradict text" in corrected_output
    assert metrics["support_found"] is False
    assert metrics["max_context_distance"] == 0.8
    assert metrics["contradictory_contexts"] == ["contradict text"]


# ===================================================================
# TEST 5: Pipeline & Wrapper execution with robust exception handling
# ===================================================================
def test_pipeline_exception_handling():
    # Mock strategy compute to throw an exception
    mock_strategy = MagicMock()
    mock_strategy.compute.side_effect = RuntimeError("Mocked compute error")
    mock_strategy_class = MagicMock(return_value=mock_strategy)

    entropy_analyzer = BankEntropyAnalyzer()
    config = AuditConfig(dissonance_strategy=mock_strategy_class)

    wrapper = IIAEService(config, entropy_analyzer)
    
    # Calling process should not raise an exception, but return CanonicalStateDTO with error
    state = wrapper.process_interaction(
        audit_input="source test",
        context_input=["context test"],
        context_axioms=["axiom test"]
    )
    
    assert isinstance(state, CanonicalStateDTO)
    assert "[CRITICAL WRAPPER ERROR] Mocked compute error" in state.data
    assert state.metadata["correction_flag"] is True
    assert "Mocked compute error" in state.metadata["audit_metrics"]["error"]


# ===================================================================
# TEST 6: Supremum (max) D_s in DissonanceStrategy
# A single highly-contradictory axiom must dominate D_s regardless
# of how many benign references are present.
# ===================================================================
@patch('idicoc_notary_core.audit.dse.semantic_strategy.SentenceTransformer')
@patch('idicoc_notary_core.audit.dse.semantic_strategy.AutoTokenizer')
@patch('idicoc_notary_core.audit.dse.semantic_strategy.AutoModelForSequenceClassification')
def test_semantic_supremum_single_critical_axiom(mock_nli_class, mock_tok_class, mock_encoder_class):
    mock_encoder = MagicMock()
    mock_encoder_class.return_value = mock_encoder
    mock_encoder.encode.return_value = np.array([0.5, 0.5, 0.0])

    mock_nli_class.return_value = MagicMock()

    config = AuditConfig(
        semantic_embedding_model="mock-embedder",
        semantic_nli_model="mock-nli",
        correction_base_tolerance=0.2,
        context_axiom_conflict_threshold=0.5,
    )

    from idicoc_notary_core.audit.dse import SemanticDissonanceStrategy
    strategy = SemanticDissonanceStrategy(config)
    strategy._cosine_distance = lambda a, b: 0.05

    call_count = [0]
    def nli_with_one_critical(premise, hypothesis):
        call_count[0] += 1
        # Only the first axiom call returns critical contradiction
        if "critical_axiom" in premise:
            return 0.95
        return 0.05

    strategy._nli_contradiction = nli_with_one_critical

    D_s, D_f, _, correction_flag, metrics = strategy.compute(
        audit_input="some output text",
        context_input=["benign context 1", "benign context 2", "benign context 3"],
        context_axioms=["critical_axiom: must not be violated", "benign axiom 1", "benign axiom 2"],
        epsilon=0.0,
    )

    # d_logic = max(max_axiom_cosine=0.05, max_axiom_contradiction=0.95) = 0.95
    assert metrics["d_logic"] == pytest.approx(0.95, abs=1e-6), (
        "El supremo debe ser dominado por la única violación axiomática crítica (0.95), "
        f"no por el promedio. d_logic={metrics['d_logic']}"
    )
    assert D_s == pytest.approx(0.95, abs=1e-6)
    assert "d_logic" in metrics


# ===================================================================
# TEST 7: algebraic_components present and correct in pipeline metadata
# ===================================================================
def test_pipeline_algebraic_components_in_metadata():
    mock_strategy = MagicMock()
    mock_strategy.compute.return_value = (
        0.3,   # D_s
        0.2,   # D_f
        "output text",
        False,
        {
            "d_logic": 0.3,
            "d_s": 0.3,
            "d_factual": 0.2,
            "d_terminal": 0.0,
            "terminality_violation": False,
            "max_axiom_distance": 0.0,
            "max_context_distance": 0.1,
            "violated_axioms": [],
            "contradictory_contexts": [],
            "support_found": True,
            "reference_count": 2,
            "snapping_flag": False,
            "correction_flag": False,
        },
    )
    mock_strategy_class = MagicMock(return_value=mock_strategy)

    entropy_analyzer = BankEntropyAnalyzer()
    config = AuditConfig(dissonance_strategy=mock_strategy_class)
    wrapper = IIAEService(config, entropy_analyzer)

    state = wrapper.process_interaction(
        audit_input="test input",
        context_input=["ctx"],
        context_axioms=["ax"],
    )

    assert isinstance(state, CanonicalStateDTO)
    ac = state.metadata.get("algebraic_components")
    assert ac is not None, "algebraic_components debe estar en el metadata del estado canónico"
    assert ac["lambda_weights"] == [0.0, 1.0, 0.0]
    assert ac["d_inv"] == 0.0
    assert ac["d_temporal"] == 0.0
    assert "d_logic" in ac
    assert abs(ac["d_logic"] - 0.3) < 1e-6


# ===================================================================
# TEST 8: verify_compliance validates coalgebraic weights and D_s=d_logic
# ===================================================================
def test_verify_compliance_algebraic_validation():
    # Stub the strategy so no ML models are loaded
    mock_strategy_class = MagicMock()
    mock_strategy_class.return_value = MagicMock()

    entropy_analyzer = BankEntropyAnalyzer()
    config = AuditConfig(rigidity_epsilon=1.0, dissonance_strategy=mock_strategy_class)
    wrapper = IIAEService(config, entropy_analyzer)

    # Case 1: valid algebraic components → should return True
    valid_state = CanonicalStateDTO(
        data="output",
        metadata={
            "d_s": 0.3,
            "algebraic_components": {
                "lambda_weights": [0.0, 1.0, 0.0],
                "d_inv": 0.0,
                "d_logic": 0.3,
                "d_temporal": 0.0,
            },
        },
    )
    assert wrapper.verify_compliance(valid_state) is True

    # Case 2: wrong lambda weights → should return False
    bad_weights_state = CanonicalStateDTO(
        data="output",
        metadata={
            "d_s": 0.3,
            "algebraic_components": {
                "lambda_weights": [1.0, 0.0, 0.0],  # wrong
                "d_inv": 0.3,
                "d_logic": 0.0,
                "d_temporal": 0.0,
            },
        },
    )
    assert wrapper.verify_compliance(bad_weights_state) is False

    # Case 3: d_s does not match lambda_logic * d_logic → should return False
    mismatched_state = CanonicalStateDTO(
        data="output",
        metadata={
            "d_s": 0.5,   # does not match d_logic=0.3
            "algebraic_components": {
                "lambda_weights": [0.0, 1.0, 0.0],
                "d_inv": 0.0,
                "d_logic": 0.3,
                "d_temporal": 0.0,
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

