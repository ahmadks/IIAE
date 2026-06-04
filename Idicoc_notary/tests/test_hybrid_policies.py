import pytest
import numpy as np
from unittest.mock import MagicMock

from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.graph.property_graph_evaluator import PropertyGraphEvaluator
from idicoc_notary_core.audit.pipeline import IDICOCPipeline
from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph


def test_unified_evaluation():
    config = AuditConfig(ctm_mode="disabled")

    # Deterministic embedder for tests to avoid external model loads
    class DummyEmbedder:
        def encode(self, text, model_name=None):
            if isinstance(text, list):
                text = " ".join(str(item) for item in text)
            text_bytes = str(text).encode("utf-8")
            vec = np.zeros(32, dtype=float)
            for idx, byte in enumerate(text_bytes[:32]):
                vec[idx] = float(byte) / 255.0
            norm = float(np.linalg.norm(vec))
            return vec / norm if norm > 0.0 else vec

    config.embedding_provider = DummyEmbedder()
    pipeline = IDICOCPipeline(config)

    # Context RAG y politicas híbridos
    context_input = ["El cielo es azul en un dia despejado."]
    context_policies = [
        "ax_num_1|El primer bin no puede superar 0.5|numeric|negative|hard|10|index=0|max=0.5",
        'ax_regex_1|No puede haber espacios|regex|negative|hard|5|pattern="\\s"',
        "ax_sem_1|El texto debe hablar de clima|semantic|affirmative|soft|5",
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
        epsilon_override=0.0,
    )

    metrics1 = res1["canonical_state"].metadata
    assert "d_context" in metrics1

    # Caso 2: Violación numérica
    bad_num_y = MockOutput("Clima_soleado", [0.6, 0.4])
    res2 = pipeline.execute(
        audit_input=bad_num_y,
        context_input=context_input,
        context_policies=context_policies,
        epsilon_override=0.0,
    )
    metrics2 = res2["canonical_state"].metadata
    assert metrics2["algebraic_components"]["d_2"] > 0.0

    # Caso 3: Violación Regex
    bad_regex_y = MockOutput("Clima soleado", [0.4, 0.6])  # Tiene espacio
    res3 = pipeline.execute(
        audit_input=bad_regex_y,
        context_input=context_input,
        context_policies=context_policies,
        epsilon_override=0.0,
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
        epsilon_override=0.0,
    )
    metrics4 = res4["canonical_state"].metadata
    assert metrics4["d_context"] > 0.4
    assert len(metrics4["contradictory_contexts"]) > 0


def test_property_graph_evaluator_respects_policy_mode_for_text_input():
    graph = PropertyGraph()
    graph.add_policy(
        "ax_numeric_hard",
        {
            "policy_type": "regex",
            "mode": "numeric",
            "polarity": "negative",
            "hardness": "hard",
            "pattern": "hola",
        },
    )
    evaluator = PropertyGraphEvaluator(graph)

    class SemanticPayload:
        def __init__(self):
            self.source_text = "hola.."
            self.text_content = "hola.."
            self.distribution = [0.1, 0.9]
            self.payload_type = "semantic"

    payload = SemanticPayload()
    assert evaluator.evaluate(payload) == 0.0


def test_pipeline_normalizes_semantic_payload_for_canonical_state():
    # Use real pipeline with lightweight deterministic embedder
    config = AuditConfig(ctm_mode="disabled")

    class DummyEmbedder:
        def encode(self, text, model_name=None):
            if isinstance(text, list):
                text = " ".join(str(item) for item in text)
            text_bytes = str(text).encode("utf-8")
            vec = np.zeros(32, dtype=float)
            for idx, byte in enumerate(text_bytes[:32]):
                vec[idx] = float(byte) / 255.0
            norm = float(np.linalg.norm(vec))
            return vec / norm if norm > 0.0 else vec

    config.embedding_provider = DummyEmbedder()
    pipeline = IDICOCPipeline(config)
    pipeline.initialize()

    class SemanticPayload:
        def __init__(self):
            self.source_text = "hola.."
            self.text_content = "hola.."
            self.distribution = np.array([0.5, 0.5])
            self.payload_type = "semantic"

    result = pipeline.execute(audit_input=SemanticPayload(), epsilon_override=1.0)
    canonical_state = result["canonical_state"]

    assert isinstance(canonical_state.data, dict)
    assert canonical_state.data["source_text"] == "hola.."
    assert canonical_state.data["payload_type"] == "semantic"
    assert canonical_state.data["distribution"] == [0.5, 0.5]
