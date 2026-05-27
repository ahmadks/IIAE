import os
import json
import pytest
import tempfile
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.base import CanonicalStateDTO
from idicoc_notary_core.audit.persistence.file_backend import FileCTMStorage
from idicoc_notary_core.audit.wrapper_pipeline import IDICOCNotaryClient
from idicoc_notary_core.kernel.custody.merkle_dag import CustodialTraceManager, MerkleDAG

def test_ctm_file_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        nodes_file = os.path.join(tmpdir, "nodes.json")
        root_file = os.path.join(tmpdir, "root.txt")
        storage = FileCTMStorage(nodes_file, root_file)
        
        # Verify initial
        assert storage.load_root_hash() is None
        assert storage.load_all_nodes() == {}
        
        # Save a node and root hash
        node_data = {"node_hash": "hash123", "parent_hashes": [], "timestamp": "now", "payload": {"foo": "bar"}}
        storage.save_node("hash123", node_data)
        storage.save_root_hash("hash123")
        
        # Verify
        assert storage.load_root_hash() == "hash123"
        assert storage.load_node("hash123")["payload"]["foo"] == "bar"
        
        # Verify reload
        storage2 = FileCTMStorage(nodes_file, root_file)
        assert storage2.load_root_hash() == "hash123"
        assert storage2.load_node("hash123")["payload"]["foo"] == "bar"

def test_pipeline_with_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        ctm_nodes = os.path.join(tmpdir, "ctm_nodes.json")
        ctm_root = os.path.join(tmpdir, "ctm_root.txt")
        
        config = AuditConfig(
            rigidity_epsilon=0.5,
            ctm_mode="full",
            ctm_nodes_path=ctm_nodes,
            ctm_root_path=ctm_root,
        )
        
        # Instantiate wrapper
        wrapper = IDICOCNotaryClient(config)
        
        # Process a valid interaction
        state = wrapper.process_interaction(
            audit_input="test transaction 123",
            context_input=["test transaction 123"],
            context_axioms=["test transaction 123"],
        )
        
        # Verify CTM nodes saved on disk
        assert os.path.exists(ctm_nodes)
        assert os.path.exists(ctm_root)
        with open(ctm_root, "r") as f:
            root_hash_1 = f.read().strip()
        assert len(root_hash_1) > 0
        
        # Reload wrapper with new instances pointing to same files
        config2 = AuditConfig(
            rigidity_epsilon=0.5,
            ctm_mode="full",
            ctm_nodes_path=ctm_nodes,
            ctm_root_path=ctm_root,
        )
        wrapper2 = IDICOCNotaryClient(config2)
        
        # The reloaded MerkleDAG must have the exact same root hash and nodes
        assert wrapper2.pipeline.ctm.root_hash == root_hash_1

def test_ctm_modes():
    config_log = AuditConfig(rigidity_epsilon=0.5, ctm_mode="log_only")
    wrapper_log = IDICOCNotaryClient(config_log)
    
    # Process interaction
    state_log = wrapper_log.process_interaction("test log", ["test log"], ["test log"])
    assert state_log.metadata["audit_metrics"] is not None
    
    result = wrapper_log.pipeline.execute("test log", ["test log"], ["test log"])
    assert result["kernel_result"] == {"status": "log_only"}
    assert result["audit_receipt"] == {"status": "log_only"}
    
    # Test disabled mode
    config_dis = AuditConfig(rigidity_epsilon=0.5, ctm_mode="disabled")
    wrapper_dis = IDICOCNotaryClient(config_dis)
    result_dis = wrapper_dis.pipeline.execute("test log", ["test log"], ["test log"])
    assert result_dis["kernel_result"] == {"status": "disabled"}
    assert result_dis["audit_receipt"] == {"status": "disabled"}
