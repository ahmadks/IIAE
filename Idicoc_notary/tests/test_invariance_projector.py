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

