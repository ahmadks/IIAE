"""
Test file for IDICOCNotaryClient with semantic profile.
"""

import math
import numpy as np

import pytest
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient


class DummyEmbedder:
    """A deterministic embedding provider for tests."""

    def encode(self, text, model_name=None):
        if isinstance(text, list):
            text = " ".join(str(item) for item in text)
        text_bytes = str(text).encode("utf-8")
        vec = np.zeros(32, dtype=float)
        for idx, byte in enumerate(text_bytes[:32]):
            vec[idx] = float(byte) / 255.0
        norm = float(np.linalg.norm(vec))
        return vec / norm if norm > 0.0 else vec


def _build_semantic_service():
    return IDICOCNotaryClient(
        AuditConfig(
            ctm_mode="disabled",
            rigidity_epsilon=0.1,
            policy_loader=None,
            policy_file_path="/tmp/nonexistent_semantic_policy_file.txt",
            embedding_provider=DummyEmbedder(),
        )
    )


def test_semantic_service_with_similar_inputs():
    """Service should admit semantically aligned inputs with low dissonance."""
    service = _build_semantic_service()

    context_input = [
        "The transaction limit is 50000.00 euros.",
        "The account balance is 120000.00 euros.",
    ]
    audit_input = "Execute a transfer of 50000.00 euros, which is within the limit."
    policy_input = ["Execute a transfer of 50000.00 euros, which is within the limit."]

    from idicoc_notary_core.audit import SemanticPayload

    canonical_state = service.process_interaction(
        audit_input=SemanticPayload(audit_input),
        context_input=context_input,
        context_policies=policy_input,
    )

    assert canonical_state is not None
    metadata = canonical_state.metadata
    assert metadata["admission_breach"] is False
    assert metadata["correction_flag"] is False
    assert metadata["d_s"] <= 0.1
    assert service.verify_compliance(canonical_state) is True
    assert metadata.get("audit_metrics", {}).get("d_s") == metadata["d_s"]


def test_semantic_service_with_hard_violation():
    """Service should reject input that violates a hard regex policy."""
    service = _build_semantic_service()

    audit_input = "Transfer 60000.00 euros, exceeding the limit."
    policy_input = [
        "ax_violation|No transfer may exceed 50000.00 euros|regex|negative|hard|10|mode=semantic|pattern=60000\\.00"
    ]

    from idicoc_notary_core.audit import SemanticPayload

    canonical_state = service.process_interaction(
        audit_input=SemanticPayload(audit_input),
        context_input=["The maximum allowed transaction amount is 50000.00 euros."],
        context_policies=policy_input,
    )

    metadata = canonical_state.metadata
    assert math.isinf(metadata["d_s"])
    assert metadata["admission_breach"] is True  # En no se corrige ex-post, se rechaza
    assert (
        metadata["correction_flag"] is False
    )  # En no se aplica corrección ex-post (SPSA / proyección)
    assert service.verify_compliance(canonical_state, tolerance=0.0) is False


def test_semantic_service_with_context_and_policy_alignment():
    """Service should accept aligned input when both context and policy are satisfied."""
    service = _build_semantic_service()

    audit_input = "Confirm transfer of 100.00 EUR within approved limits."
    context_input = ["Approved transfers must remain below the 100.00 EUR ceiling."]
    policy_input = ["Confirmed transfer stays within the approved limit."]

    from idicoc_notary_core.audit import SemanticPayload

    canonical_state = service.process_interaction(
        audit_input=SemanticPayload(audit_input),
        context_input=context_input,
        context_policies=policy_input,
    )

    metadata = canonical_state.metadata
    assert metadata["admission_breach"] is False
    assert metadata["correction_flag"] is False
    assert metadata["d_s"] <= 0.1
    assert service.verify_compliance(canonical_state, tolerance=0.15) is True
