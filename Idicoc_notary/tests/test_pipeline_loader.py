import pytest
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.pipeline import IDICOCPipeline
from idicoc_notary_core.audit.graph.loader import InlineAxiomLoader

def test_pipeline_loads_axioms_on_init():
    axioms = [{"id": "test_ax_1", "text": "Test axiom", "axiom_type": "world"}]
    config = AuditConfig()
    config.axiom_loader = InlineAxiomLoader(axioms)
    
    pipeline = IDICOCPipeline(config)
    
    # Graph should have the axiom loaded
    active = pipeline.graph.get_active_axioms()
    assert len(active) == 1
    assert active[0]["id"] == "test_ax_1"
    assert "embedding" in active[0], "Embedding should have been precomputed"

def test_execute_does_not_mutate_graph():
    config = AuditConfig()
    config.axiom_loader = InlineAxiomLoader([])
    pipeline = IDICOCPipeline(config)
    
    assert len(pipeline.graph.nodes) == 0
    
    # Execute with dynamic context
    pipeline.execute(
        audit_input="hello",
        context_input=["new context"],
        context_axioms=["dynamic axiom"]
    )
    
    # Graph must remain empty
    assert len(pipeline.graph.nodes) == 0
