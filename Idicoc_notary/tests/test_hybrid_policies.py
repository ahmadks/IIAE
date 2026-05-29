import pytest
import numpy as np
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.pipeline import IDICOCPipeline

def test_unified_evaluation():
    config = AuditConfig()
    pipeline = IDICOCPipeline(config)
    
    # Context RAG y politicas híbridos
    context_input = ["El cielo es azul en un dia despejado."]
    context_policies = [
        "ax_num_1|El primer bin no puede superar 0.5|numeric|negative|hard|10|index=0|max=0.5",
        "ax_regex_1|No puede haber espacios|regex|negative|hard|5|pattern=\"\\s\"",
        "ax_sem_1|El texto debe hablar de clima|semantic|affirmative|soft|5"
    ]
    
    pipeline.initialize()
    
    class MockOutput:
        def __init__(self, text, vec):
            self.content = text
            self.text_content = text
            self.distribution = vec
            
    # Caso 1: Todo correcto.
    # vec[0] <= 0.5 (0.4)
    # text = "Clima_soleado" (sin espacios, habla de clima, no contradice "cielo azul")
    good_y = MockOutput("Clima_soleado", [0.4, 0.6])
    
    # Evaluamos
    res1 = pipeline.execute(
        audit_input=good_y,
        context_input=context_input,
        context_policies=context_policies,
        epsilon_override=0.0
    )
    
    metrics1 = res1["canonical_state"].metadata
    assert "d_context" in metrics1
    
    # Caso 2: Violación numérica
    bad_num_y = MockOutput("Clima_soleado", [0.6, 0.4])
    res2 = pipeline.execute(
        audit_input=bad_num_y,
        context_input=context_input,
        context_policies=context_policies,
        epsilon_override=0.0
    )
    metrics2 = res2["canonical_state"].metadata
    assert metrics2["algebraic_components"]["d_2"] > 0.0
    
    # Caso 3: Violación Regex
    bad_regex_y = MockOutput("Clima soleado", [0.4, 0.6]) # Tiene espacio
    res3 = pipeline.execute(
        audit_input=bad_regex_y,
        context_input=context_input,
        context_policies=context_policies,
        epsilon_override=0.0
    )
    metrics3 = res3["canonical_state"].metadata
    assert metrics3["algebraic_components"]["d_2"] > 0.0
    
    # Caso 4: Violación semántica RAG (Contradicción)
    # The MNLI model is English (distilbert-base-uncased-mnli)
    clear_context = ["The cat is sleeping on the mat."]
    bad_rag_y = MockOutput("The cat is running outside.", [0.4, 0.6])
    res4 = pipeline.execute(
        audit_input=bad_rag_y,
        context_input=clear_context,
        context_policies=context_policies,
        epsilon_override=0.0
    )
    metrics4 = res4["canonical_state"].metadata
    assert metrics4["d_context"] > 0.4
    assert len(metrics4["contradictory_contexts"]) > 0
