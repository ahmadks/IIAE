import pytest
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.utils.embedding_utils import compute_embedding_signature
import hashlib
import json


def test_signature_deterministic():
    sig1 = compute_embedding_signature("modelA")
    sig2 = compute_embedding_signature("modelA")
    assert sig1 == sig2


def test_signature_differs_on_model():
    sig1 = compute_embedding_signature("modelA")
    sig2 = compute_embedding_signature("modelB")
    assert sig1 != sig2


def test_config_auto_computes_signature():
    config = AuditConfig(semantic_embedding_model="test-model")
    assert config.embedding_signature is not None


def test_config_strict_mode():
    config = AuditConfig(
        semantic_embedding_model="test-model",
        embedding_signature="expected_sig",
        strict_embedding_signature=True,
    )
    assert config.embedding_signature == "expected_sig"
    assert config.strict_embedding_signature is True
