"""
Test file for IDICOCNotaryClient with semantic profile.
"""

import math
import numpy as np
import pytest

from idicoc_notary.config import AuditConfig
from idicoc_notary import IDICOCNotaryClient


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

    res = service.auditar(
        user_prompt="Mock numeric distribution input",
        rag_context="\n".join(context_input),
        llm_output=audit_input,
        context_policies=policy_input,
    )

    assert res is not None
    assert res.is_admitted is True
    assert res.dissonance_ds <= 0.15
    assert res.metrics.get("d_s") == res.dissonance_ds


def test_semantic_service_with_hard_violation():
    """Service should reject input that violates a hard regex policy."""
    service = _build_semantic_service()

    audit_input = "Transfer 60000.00 euros, exceeding the limit."
    policy_input = [
        "[HARD] No transfer may exceed 50000.00 euros."
    ]

    res = service.auditar(
        user_prompt="Incompatible transfer request",
        rag_context="The maximum allowed transaction amount is 50000.00 euros.",
        llm_output=audit_input,
        context_policies=policy_input,
    )

    assert math.isinf(res.dissonance_ds)
    assert res.is_admitted is False


def test_semantic_service_with_context_and_policy_alignment():
    """Service should accept aligned input when both context and policy are satisfied."""
    service = _build_semantic_service()

    audit_input = "Confirm transfer of 100.00 EUR within approved limits."
    context_input = ["Approved transfers must remain below the 100.00 EUR ceiling."]
    policy_input = ["Confirmed transfer stays within the approved limit."]

    res = service.auditar(
        user_prompt="EUR transfer",
        rag_context="\n".join(context_input),
        llm_output=audit_input,
        context_policies=policy_input,
    )

    assert res.is_admitted is True
    assert res.dissonance_ds <= 0.15
