import os
import json
import numpy as np
import pytest
from datetime import datetime, timezone

from idicoc_notary_core import AuditConfig, IDICOCNotaryClient
from idicoc_notary_core.audit.pipeline import IDICOCPipeline
from idicoc_notary_core.utils.embedding_service import EmbeddingService


# -----------------------------------------------------------------------------
# 1. MOCK EMBEDDING PROVIDER FOR ISOLATED RUNTIMES
# -----------------------------------------------------------------------------
class MockEmbeddingProvider:
    def __init__(self, vector: np.ndarray):
        self.vector = vector
        self.encode_called = 0

    def encode(self, text, model_name=None, normalize_embeddings=True):
        self.encode_called += 1
        return self.vector


def test_mock_embedding_provider_injection(tmp_path):
    # Crear un vector simulado de 4 dimensiones para alinearse con k
    custom_vector = np.array([0.1, 0.4, 0.4, 0.1])
    provider = MockEmbeddingProvider(custom_vector)

    nodes_path = str(tmp_path / "ctm_nodes.json")
    root_path = str(tmp_path / "ctm_root.txt")

    config = AuditConfig(
        instance_name="mock-provider-test",
        client_id="test-provider-session",
        ctm_mode="log_only",
        rigidity_epsilon=0.20,
        embedding_provider=provider,
        ctm_nodes_path=nodes_path,
        ctm_root_path=root_path,
    )

    client = IDICOCNotaryClient(config)

    # Verificar que el proveedor de embeddings en EmbeddingService es el nuestro
    assert EmbeddingService._provider is provider

    # Ejecutar una codificación a través de EmbeddingService y verificar llamada
    res = EmbeddingService().encode("test text")
    assert np.allclose(res, custom_vector)
    assert provider.encode_called >= 1


# -----------------------------------------------------------------------------
# 2. DYNAMIC CONTEXT POLICYS LIGAND LIFECYCLE
# -----------------------------------------------------------------------------
def test_dynamic_context_policies_injection_and_cleanup(tmp_path):
    nodes_path = str(tmp_path / "ctm_nodes.json")
    root_path = str(tmp_path / "ctm_root.txt")

    custom_vector = np.array([0.25, 0.25, 0.25, 0.25])
    provider = MockEmbeddingProvider(custom_vector)

    config = AuditConfig(
        instance_name="dynamic-policies-test",
        client_id="test-session",
        ctm_mode="log_only",
        rigidity_epsilon=0.20,
        embedding_provider=provider,
        ctm_nodes_path=nodes_path,
        ctm_root_path=root_path,
    )

    client = IDICOCNotaryClient(config)

    # Policyas dinámicos temporales a inyectar
    dynamic_policies = [
        "ax_dyn_1|Dynamic test policy 1|fact|negative|hard|8",
        {
            "id": "ax_dyn_2",
            "text": "Dynamic test policy 2",
            "policy_type": "fact",
            "polarity": "negative",
            "hardness": "soft",
            "priority": 5,
        }
    ]

    # Ejecutar el pipeline pasándole los politicas dinámicos
    result = client.process_interaction(
        audit_input=custom_vector,
        context_policies=dynamic_policies,
    )

    # Verificar que los politicas dinámicos fueron reportados en el resultado
    assert any("ax_dyn_1" in str(ax) for ax in result.source_policies)
    assert any("ax_dyn_2" in str(ax) for ax in result.source_policies)

    # Verificar que el PropertyGraph esté completamente limpio y no tenga rastro de ellos
    assert client.pipeline is not None
    assert "ax_dyn_1" not in client.pipeline.graph.nodes
    assert "ax_dyn_2" not in client.pipeline.graph.nodes


# -----------------------------------------------------------------------------
# 3. ROBUST ENTERPRISE WAL RECONCILIATION
# -----------------------------------------------------------------------------
def test_wal_automatic_reconciliation(tmp_path):
    nodes_path = str(tmp_path / "ctm_nodes.json")
    root_path = str(tmp_path / "ctm_root.txt")
    wal_path = str(tmp_path / "ctm_wal.log")

    custom_vector = np.array([0.25, 0.25, 0.25, 0.25])
    provider = MockEmbeddingProvider(custom_vector)

    # 1. Forzar una entrada pendiente en el archivo del WAL directamente
    from idicoc_notary_core.audit.persistence.ctm_wal import WriteAheadLogger
    wal = WriteAheadLogger(wal_path)
    
    tx_payload = {
        "canonical_state": [0.25, 0.25, 0.25, 0.25],
        "dissonance": 0.0,
        "invariant_state_hash": "dummy_inv_hash",
        "property_graph_hash": "dummy_graph_hash",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    wal.write("tx_reconcile_test_123", tx_payload)

    # 2. Inicializar el pipeline con este archivo WAL pre-existente
    config = AuditConfig(
        instance_name="wal-reconcile-test",
        client_id="test-session",
        ctm_mode="full",
        embedding_provider=provider,
        ctm_nodes_path=nodes_path,
        ctm_root_path=root_path,
    )
    # Sobrescribimos el path del WAL
    config.ctm_wal_path = wal_path

    client = IDICOCNotaryClient(config)

    # 3. La inicialización debe haber reconciliado automáticamente la transacción
    # y marcado su estado como COMPLETED en el WAL
    assert client.pipeline is not None, "El pipeline debe estar inicializado"
    pending = client.pipeline.wal.recover_pending_transactions()
    assert "tx_reconcile_test_123" not in pending
