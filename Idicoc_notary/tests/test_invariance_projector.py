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
