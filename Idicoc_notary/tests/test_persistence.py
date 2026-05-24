import os
import json
import pytest
import tempfile
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.base import BankEntropyAnalyzer, CanonicalStateDTO
from idicoc_notary_core.audit.persistence.file_backend import FileAEMStorage, FileCTMStorage
from idicoc_notary_core.audit.wrapper_pipeline import IIAEService
from idicoc_notary_core.kernel.admission.aem import AnomalousEventManager
from idicoc_notary_core.kernel.custody.merkle_dag import CustodialTraceManager, MerkleDAG

def test_aem_file_persistence():
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "aem_entropy.json")
        storage = FileAEMStorage(filepath)
        
        # Verify initial empty structure
        events = storage.load_all_events()
        assert events == {"DISCARDED_NOISE": [], "RECOVERABLE_NOISE": [], "ADMITTED": []}
        
        # Save an event
        event = {"category": "ADMITTED", "entropy": 0.1, "structural": "hello", "noise": "world"}
        storage.save_entropy_event(event)
        
        # Verify saved in memory
        events = storage.load_all_events()
        assert len(events["ADMITTED"]) == 1
        assert events["ADMITTED"][0]["structural"] == "hello"
        
        # Verify written to disk
        with open(filepath, "r") as f:
            disk_data = json.load(f)
        assert len(disk_data["ADMITTED"]) == 1
        
        # Reload new storage instance from same file
        storage2 = FileAEMStorage(filepath)
        assert len(storage2.load_all_events()["ADMITTED"]) == 1
        
        # Clear
        storage.clear()
        assert len(storage.load_all_events()["ADMITTED"]) == 0
        with open(filepath, "r") as f:
            disk_data2 = json.load(f)
        assert len(disk_data2["ADMITTED"]) == 0

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
        aem_path = os.path.join(tmpdir, "aem.json")
        ctm_nodes = os.path.join(tmpdir, "ctm_nodes.json")
        ctm_root = os.path.join(tmpdir, "ctm_root.txt")
        
        aem_storage = FileAEMStorage(aem_path)
        ctm_storage = FileCTMStorage(ctm_nodes, ctm_root)
        
        config = AuditConfig(audit_mode="mathematical", rigidity_epsilon=0.5, ctm_mode="full")
        analyzer = BankEntropyAnalyzer()
        
        # Instantiate wrapper with storage backends
        wrapper = IIAEService(config, analyzer, aem_storage=aem_storage, ctm_storage=ctm_storage)
        
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
        
        # Verify AEM events saved on disk (segregated)
        with open(aem_path, "r") as f:
            aem_data = json.load(f)
        assert len(aem_data["DISCARDED_NOISE"]) == 1
        
        # Reload wrapper with new instances pointing to same files
        aem_storage2 = FileAEMStorage(aem_path)
        ctm_storage2 = FileCTMStorage(ctm_nodes, ctm_root)
        wrapper2 = IIAEService(config, analyzer, aem_storage=aem_storage2, ctm_storage=ctm_storage2)
        
        # The reloaded MerkleDAG must have the exact same root hash and nodes
        assert wrapper2.pipeline.ctm.root_hash == root_hash_1
        assert len(wrapper2.pipeline.aem.entropy_map["DISCARDED_NOISE"]) == 1

def test_ctm_modes():
    config_log = AuditConfig(audit_mode="mathematical", rigidity_epsilon=0.5, ctm_mode="log_only")
    analyzer = BankEntropyAnalyzer()
    wrapper_log = IIAEService(config_log, analyzer)
    
    # Process interaction
    state_log = wrapper_log.process_interaction("test log", ["test log"], ["test log"])
    assert state_log.metadata["audit_metrics"] is not None
    
    result = wrapper_log.pipeline.execute("test log", ["test log"], ["test log"])
    assert result["kernel_result"] == {"status": "log_only"}
    assert result["audit_receipt"] == {"status": "log_only"}
    
    # Test disabled mode
    config_dis = AuditConfig(audit_mode="mathematical", rigidity_epsilon=0.5, ctm_mode="disabled")
    wrapper_dis = IIAEService(config_dis, analyzer)
    result_dis = wrapper_dis.pipeline.execute("test log", ["test log"], ["test log"])
    assert result_dis["kernel_result"] == {"status": "disabled"}
    assert result_dis["audit_receipt"] == {"status": "disabled"}
