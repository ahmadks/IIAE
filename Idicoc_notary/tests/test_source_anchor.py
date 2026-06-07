import os
import json
import pytest
import tempfile
import numpy as np

from idicoc_core.config import AuditConfig
from idicoc_core.kernel.source.anchor import SourceAnchor
from idicoc_core.pipeline.orchestrator import AuditPipeline
from idicoc_core import NotaryClient

def test_source_anchor_properties():
    """Verify that SourceAnchor has correct properties and is immutable."""
    anchor = SourceAnchor()
    assert len(anchor.fingerprint) == 64
    assert anchor.fingerprint == anchor.identity_hash
    assert anchor.fingerprint == "dea6fb7a96d644da606b3efe3cc43c3d33cb14160936e44ca5af0b2aff0047e0"
    assert "SourceAnchor" in repr(anchor)

def test_record_k_fingerprint_enabled():
    """Verify that SourceAnchor fingerprint is recorded in WAL and CTM when enabled."""
    class DummyEmbedder:
        def encode(self, text, model_name=None):
            return np.zeros(384, dtype=float)

    with tempfile.TemporaryDirectory() as tmpdir:
        ctm_nodes = os.path.join(tmpdir, "ctm_nodes.json")
        ctm_root = os.path.join(tmpdir, "ctm_root.txt")
        ctm_wal = os.path.join(tmpdir, "ctm_wal.log")
        
        config = AuditConfig(
            ctm_mode="full",
            ctm_nodes_path=ctm_nodes,
            ctm_root_path=ctm_root,
            ctm_wal_path=ctm_wal,
            record_k_fingerprint=True,
            embedding_provider=DummyEmbedder(),
        )
        
        pipeline = AuditPipeline(config)
        assert pipeline.source_anchor is not None
        
        # Execute audit
        res = pipeline.execute_audit(
            user_prompt="Audit connection prompt",
            rag_context="RAG context",
            llm_output="Output aligned with context",
        )
        
        # Verify CTM nodes log contains fingerprint
        assert os.path.exists(ctm_nodes)
        nodes_data = []
        with open(ctm_nodes, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    nodes_data.append(json.loads(line))
        
        found_in_ctm = False
        for node in nodes_data:
            payload = node.get("payload", {})
            logical_payload = payload.get("payload", {})
            if "k_fingerprint" in logical_payload:
                assert logical_payload["k_fingerprint"] == pipeline.source_anchor.fingerprint
                assert logical_payload["k_anchor"] == pipeline.source_anchor.fingerprint
                found_in_ctm = True
                
        assert found_in_ctm is True

        # Verify WAL contains fingerprint
        assert os.path.exists(ctm_wal)
        found_in_wal = False
        with open(ctm_wal, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    wal_entry = json.loads(line)
                    tx_payload = wal_entry.get("payload", {})
                    if "k_fingerprint" in tx_payload:
                        assert tx_payload["k_fingerprint"] == pipeline.source_anchor.fingerprint
                        found_in_wal = True
                        
        assert found_in_wal is True

def test_record_k_fingerprint_disabled():
    """Verify that SourceAnchor fingerprint is not recorded when record_k_fingerprint=False."""
    class DummyEmbedder:
        def encode(self, text, model_name=None):
            return np.zeros(384, dtype=float)

    with tempfile.TemporaryDirectory() as tmpdir:
        ctm_nodes = os.path.join(tmpdir, "ctm_nodes.json")
        ctm_root = os.path.join(tmpdir, "ctm_root.txt")
        ctm_wal = os.path.join(tmpdir, "ctm_wal.log")
        
        config = AuditConfig(
            ctm_mode="full",
            ctm_nodes_path=ctm_nodes,
            ctm_root_path=ctm_root,
            ctm_wal_path=ctm_wal,
            record_k_fingerprint=False,
            embedding_provider=DummyEmbedder(),
        )
        
        pipeline = AuditPipeline(config)
        assert pipeline.source_anchor is None
        
        # Execute audit
        res = pipeline.execute_audit(
            user_prompt="Audit connection prompt",
            rag_context="RAG context",
            llm_output="Output aligned with context",
        )
        
        # Verify CTM nodes do not contain fingerprint
        assert os.path.exists(ctm_nodes)
        nodes_data = []
        with open(ctm_nodes, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    nodes_data.append(json.loads(line))
        
        for node in nodes_data:
            payload = node.get("payload", {})
            logical_payload = payload.get("payload", {})
            assert "k_fingerprint" not in logical_payload
            assert "k_anchor" not in logical_payload

        # Verify WAL does not contain fingerprint
        assert os.path.exists(ctm_wal)
        with open(ctm_wal, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    wal_entry = json.loads(line)
                    tx_payload = wal_entry.get("payload", {})
                    assert "k_fingerprint" not in tx_payload
