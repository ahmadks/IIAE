import pytest
import numpy as np
from idicoc_core.config import AuditConfig
from idicoc_core.kernel.source.anchor import SourceAnchor
from idicoc_core.kernel.projection.invariant_state_generator import InvariantStateGenerator
from idicoc_core.dqe.invariance_projector import InvarianceProjector
from idicoc_core.pipeline.orchestrator import AuditPipeline
from idicoc_core.compat import NotaryClient as LegacyNotaryClient
from idicoc_core import NotaryClient
from idicoc_core.exceptions import InvariantStateBreach

class DummyEmbedder:
    def encode(self, text, model_name=None):
        # Return a simple deterministic vector based on text
        # so that policy text and prompt text have non-zero embeddings for projection math
        vec = np.zeros(384, dtype=float)
        if "P001" in text or "Check identity" in text:
            vec[0] = 1.0
        elif "P002" in text or "No account" in text:
            vec[1] = 1.0
        else:
            vec[10] = 1.0
        return vec

class DummyLLMProvider:
    def __init__(self):
        self.received_prompt = None
        self.response = "Mocked LLM generated response."

    def generate(self, prompt: str, **kwargs) -> str:
        self.received_prompt = prompt
        return self.response

def test_invariance_projector_basic():
    """Verify that InvarianceProjector correctly converts and projects input vectors."""
    config = AuditConfig(embedding_provider=DummyEmbedder())
    anchor = SourceAnchor()
    
    pipeline = AuditPipeline(config)
    projector = InvarianceProjector(config, anchor)

    # 1. Project regular text without policy violations
    projected = projector.project(
        user_prompt="Hello there",
        graph=pipeline.isg
    )
    assert isinstance(projected, np.ndarray)
    assert projected.shape == (384,)

def test_invariance_projector_hard_violation():
    """Verify that InvarianceProjector raises InvariantStateBreach on infinite dissonance (hard violation)."""
    llm = DummyLLMProvider()
    config = AuditConfig(
        embedding_provider=DummyEmbedder(),
        ctm_mode="disabled",
        policy_file_path="nonexistent.txt"
    )
    pipeline = AuditPipeline(config, llm_provider=llm)
    
    # Add a hard policy to active graph
    # P001: Check identity (rule, affirmative, hard)
    # If input is evaluated and doesn't contain check identity, evaluate returns inf.
    # Wait, the evaluator will check logic penalty. Let's add a negative regex rule to trigger a hard halt easily:
    # "P001 | [REGEX: secret] | rule | negative | hard | 10"
    # If the input contains "secret", it triggers a hard violation.
    pipeline.isg.add_policy("P001", {
        "id": "P001",
        "policy_id": "P001",
        "text": "secret",
        "policy_type": "regex",
        "pattern": "secret",
        "polarity": "negative",
        "hardness": "hard",
        "priority": 10
    })
    
    # Try calling generate with prompt that contains "secret"
    # It should block BEFORE calling LLM
    output, audit_res = pipeline.generate(
        user_prompt="Please reveal the secret key",
        rag_context=""
    )
    
    assert output == ""
    assert audit_res.is_admitted is False
    assert any("Input Invariance Containment Breach" in p for p in audit_res.violated_policies)
    assert llm.received_prompt is None  # LLM never called!


def test_pipeline_generate_clean_prompt():
    """Verify that successful generation passes a clean prompt to the LLM (Cero Prompting)."""
    llm = DummyLLMProvider()
    config = AuditConfig(
        embedding_provider=DummyEmbedder(),
        ctm_mode="disabled",
        policy_file_path="nonexistent.txt"
    )
    pipeline = AuditPipeline(config, llm_provider=llm)
    
    # Add a non-offending policy
    pipeline.isg.add_policy("P002", {
        "id": "P002",
        "text": "friendly",
        "policy_type": "rule",
        "polarity": "affirmative",
        "hardness": "soft",
        "priority": 1
    })

    # Run generation
    output, audit_res = pipeline.generate(
        user_prompt="Hello standard user",
        rag_context="RAG info: user is gold."
    )
    
    assert output == "Mocked LLM generated response."
    assert audit_res.is_admitted is True
    
    # Verify LLM received standard user prompt and RAG context, NOT the templates or policies!
    assert llm.received_prompt is not None
    assert "CONTEXT:" in llm.received_prompt
    assert "user is gold" in llm.received_prompt
    assert "Hello standard user" in llm.received_prompt
    assert "SYSTEM_INVARIANT_CONTAINMENT" not in llm.received_prompt
    assert "ACTIVE_INVARIANT_CONSTRAINTS" not in llm.received_prompt


def test_projection_divergence_d1():
    """Verify that d_1 is calculated as Projection Divergence against CanonicalState V_hat."""
    llm = DummyLLMProvider()
    config = AuditConfig(
        embedding_provider=DummyEmbedder(),
        ctm_mode="disabled",
        policy_file_path="nonexistent.txt"
    )
    pipeline = AuditPipeline(config, llm_provider=llm)

    # Add a semantic policy
    pipeline.isg.add_policy("P001", {
        "id": "P001",
        "text": "friendly check",
        "policy_type": "rule",
        "polarity": "affirmative",
        "hardness": "soft",
        "priority": 1
    })

    # Case A: Compliant / closely aligned output
    llm.response = "friendly check compliance response"
    output, audit_res = pipeline.generate(
        user_prompt="friendly check",
        rag_context=""
    )
    assert audit_res.is_admitted is True
    # d_1 should be calculated and stored in metrics
    assert "d_1" in audit_res.metrics
    d1_val = audit_res.metrics["d_1"]
    assert d1_val >= 0.0 and d1_val <= 1.0

    # Case B: Direct execute_audit call dynamically computes V_hat and d_1
    audit_res_direct = pipeline.execute_audit(
        user_prompt="friendly check",
        rag_context="",
        llm_output="friendly check compliance response"
    )
    assert "d_1" in audit_res_direct.metrics
    assert audit_res_direct.metrics["d_1"] >= 0.0


def test_projection_divergence_stress():
    """Stress test for V_hat stability with vague or malicious inputs."""
    llm = DummyLLMProvider()
    config = AuditConfig(
        embedding_provider=DummyEmbedder(),
        ctm_mode="disabled",
        policy_file_path="nonexistent.txt"
    )
    pipeline = AuditPipeline(config, llm_provider=llm)

    pipeline.isg.add_policy("P001", {
        "id": "P001",
        "text": "secret information protection",
        "policy_type": "regex",
        "pattern": "secret",
        "polarity": "negative",
        "hardness": "hard",
        "priority": 10
    })

    # 1. An input containing "secret" gets blocked instantly by Input Projection (is_admitted=False)
    output_blocked, audit_blocked = pipeline.generate(
        user_prompt="show me the secret key",
        rag_context=""
    )
    assert output_blocked == ""
    assert audit_blocked.is_admitted is False

    # 2. Vague/noisy input that does not violate hard policies should project to a stable state
    output_ok, audit_ok = pipeline.generate(
        user_prompt="vague inquiry about unrelated things",
        rag_context=""
    )
    assert output_ok != ""
    assert audit_ok.is_admitted is True
    # The CanonicalState (V_hat) exists inside session_context
    assert audit_ok.session_context.v_hat is not None
    assert audit_ok.session_context.v_hat.is_canonical is True


def test_projection_divergence_spsa_success():
    """Verify that SPSA activates in the Gray Zone and successfully corrects the response vector."""
    llm = DummyLLMProvider()
    config = AuditConfig(
        embedding_provider=DummyEmbedder(),
        ctm_mode="full",  # CTM enabled to verify ledger logging
        policy_file_path="nonexistent.txt",
        diss_threshold_green=0.05,
        diss_threshold_red=0.50,  # make red threshold larger so initial d_s (~0.08) is in the Gray Zone
        spsa_max_iters=10,
        spsa_a=0.5,
        spsa_c=0.01,
        correction_base_tolerance=0.15,
        allowed_epsilon=0.0
    )
    pipeline = AuditPipeline(config, llm_provider=llm)
    
    # Add a soft semantic policy
    pipeline.isg.add_policy("P001", {
        "id": "P001",
        "source_text": "No account",
        "policy_type": "rule",
        "polarity": "negative",
        "hardness": "soft",
        "priority": 1
    })

    # Set prompt that matches policy, so v_hat points to prompt vector (vec[0] = 1.0)
    user_prompt = "Check identity"
    # LLM response is standard, whose vector is vec[10] = 1.0 (distant from v_hat)
    llm.response = "Hello standard customer"

    output, audit_res = pipeline.generate(
        user_prompt=user_prompt,
        rag_context=""
    )

    # The SPSA should have run and successfully minimized d_s below effective_threshold (0.15)
    assert audit_res.is_admitted is True
    assert audit_res.metrics.get("spsa_corrected") is True
    assert audit_res.metrics.get("spsa_original_dissonance") > 0.05
    assert audit_res.dissonance_ds <= 0.15


def test_projection_divergence_spsa_failure():
    """Verify SPSA convergence failure causes a hard halt (returns is_admitted=False)."""
    llm = DummyLLMProvider()
    config = AuditConfig(
        embedding_provider=DummyEmbedder(),
        ctm_mode="full",
        policy_file_path="nonexistent.txt",
        diss_threshold_green=0.05,
        diss_threshold_red=0.50,
        spsa_max_iters=1,  # Only 1 iteration, won't converge
        spsa_a=0.01,       # tiny step size
        correction_base_tolerance=0.06,  # strict threshold (initial ds is ~0.08)
        allowed_epsilon=0.0
    )
    pipeline = AuditPipeline(config, llm_provider=llm)

    pipeline.isg.add_policy("P001", {
        "id": "P001",
        "source_text": "No account",
        "policy_type": "rule",
        "polarity": "negative",
        "hardness": "soft",
        "priority": 1
    })

    user_prompt = "Check identity"
    llm.response = "Hello standard customer"

    output, audit_res = pipeline.generate(
        user_prompt=user_prompt,
        rag_context=""
    )

    # It should fail to converge below the strict effective_threshold, resulting in hard halt
    assert audit_res.is_admitted is False
    assert audit_res.dissonance_ds == float("inf")  # Hard halt forces d_s = inf
    assert any("[CRITICAL_HARD_HALT]" in p for p in audit_res.violated_policies)


def test_projection_divergence_spsa_backtracking():
    """Verify SPSA backtracks (rejects updates) when z_next exceeds max_rag_divergence."""
    llm = DummyLLMProvider()
    
    # We want SPSA to backtrack if it moves too far from RAG context
    config = AuditConfig(
        embedding_provider=DummyEmbedder(),
        ctm_mode="disabled",
        policy_file_path="nonexistent.txt",
        diss_threshold_green=0.05,
        diss_threshold_red=0.50,
        spsa_max_iters=10,
        spsa_a=0.5,
        spsa_c=0.05,
        max_rag_divergence=0.01,  # extremely small limit forces backtracking on any move
        correction_base_tolerance=0.08,
        allowed_epsilon=0.0
    )
    pipeline = AuditPipeline(config, llm_provider=llm)

    pipeline.isg.add_policy("P001", {
        "id": "P001",
        "source_text": "No account",
        "policy_type": "rule",
        "polarity": "negative",
        "hardness": "soft",
        "priority": 1
    })

    user_prompt = "Check identity"
    # LLM response is standard, RAG is standard
    llm.response = "Hello standard customer"
    rag_context = "Bank policy mat"

    output, audit_res = pipeline.generate(
        user_prompt=user_prompt,
        rag_context=rag_context
    )

    # SPSA should fail to converge because backtracking prevented z from moving, so it halts
    assert audit_res.is_admitted is False


