import pytest
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.pipeline import IDICOCPipeline
from idicoc_notary_core.audit.graph.loader import InlinePolicyLoader

def test_pipeline_loads_policies_on_init():
    policies = [{"id": "test_ax_1", "text": "Test policy", "policy_type": "world"}]
    config = AuditConfig()
    config.policy_loader = InlinePolicyLoader(policies)
    
    pipeline = IDICOCPipeline(config)
    
    # Graph should have the policy loaded
    active = pipeline.graph.get_active_policies()
    assert len(active) == 1
    assert active[0]["id"] == "test_ax_1"
    assert "embedding" in active[0], "Embedding should have been precomputed"

def test_execute_does_not_mutate_graph():
    config = AuditConfig()
    config.policy_loader = InlinePolicyLoader([])
    pipeline = IDICOCPipeline(config)
    
    assert len(pipeline.graph.nodes) == 0
    
    # Execute with dynamic context
    pipeline.execute(
        audit_input="hello",
        context_input=["new context"],
        context_policies=["dynamic policy"]
    )
    
    # Graph must remain empty
    assert len(pipeline.graph.nodes) == 0
