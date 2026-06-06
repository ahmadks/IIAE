import pytest
from idicoc_notary.config import AuditConfig
from idicoc_notary.pipeline.orchestrator import AuditPipeline
from idicoc_notary.isg.loader import InlinePolicyLoader

def test_pipeline_loads_policies_on_init():
    policies = [{"id": "test_ax_1", "text": "Test policy", "policy_type": "world"}]
    config = AuditConfig()
    config.policy_loader = InlinePolicyLoader(policies)
    
    pipeline = AuditPipeline(config)
    
    # Graph should have the policy loaded
    active = pipeline.isg.get_active_policies()
    assert len(active) == 1
    assert active[0]["id"] == "test_ax_1"
    assert "embedding" in active[0], "Embedding should have been precomputed"

def test_execute_does_not_mutate_graph():
    config = AuditConfig()
    config.policy_loader = InlinePolicyLoader([])
    pipeline = AuditPipeline(config)
    
    assert len(pipeline.isg.nodes) == 0
    
    # Execute with dynamic context
    pipeline.execute_audit(
        user_prompt="hello",
        rag_context="new context",
        llm_output="response",
        context_policies=["dynamic policy"]
    )
    
    # Graph must remain empty
    assert len(pipeline.isg.nodes) == 0

