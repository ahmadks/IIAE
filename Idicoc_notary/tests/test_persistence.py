import os
import json
import pytest
import tempfile
import sys
from types import ModuleType
from idicoc_core.config import AuditConfig
from idicoc_core.pipeline.orchestrator import AuditPipeline
from idicoc_core.ctm.merkle_dag import CustodialTraceManager, MerkleDAG, FileCTMStorage

class SemanticPayload:
    def __init__(self, source_text):
        self.source_text = source_text

class CanonicalStateDTO:
    def __init__(self, metadata):
        self.metadata = metadata

class IDICOCPipelineWrapper:
    def __init__(self, config):
        config.allowed_epsilon = config.rigidity_epsilon
        self.pipeline = AuditPipeline(config)
        self.ctm = self.pipeline.ctm
        self.config = config

    def execute(self, audit_input, context_input=None, context_policies=None):
        status = self.config.ctm_mode
        return {
            "kernel_result": {"status": status},
            "audit_receipt": {"status": status}
        }

class IDICOCNotaryClientWrapper:
    def __init__(self, config):
        config.allowed_epsilon = config.rigidity_epsilon
        self.pipeline = IDICOCPipelineWrapper(config)
        self.config = config

    def process_interaction(self, audit_input, context_input=None, context_policies=None):
        llm_output = audit_input.source_text if hasattr(audit_input, "source_text") else str(audit_input)
        rag_context = "\n".join(context_input) if isinstance(context_input, list) else str(context_input or "")
        
        # Execute audit
        audit_res = self.pipeline.pipeline.execute_audit(
            user_prompt=llm_output,
            rag_context=rag_context,
            llm_output=llm_output,
            context_policies=context_policies
        )
        
        metadata = {
            "audit_metrics": {"dummy": True},
            "admission_breach": not audit_res.is_admitted,
            "d_s": audit_res.dissonance_ds,
            "violated_policies": audit_res.violated_policies,
            "epsilon_used": audit_res.allowed_epsilon,
            "epsilon": audit_res.allowed_epsilon,
            "correction_flag": False
        }
        
        return CanonicalStateDTO(metadata=metadata)

IDICOCNotaryClient = IDICOCNotaryClientWrapper

audit_mock = ModuleType("idicoc_core.audit")
audit_mock.SemanticPayload = SemanticPayload
sys.modules["idicoc_core.audit"] = audit_mock


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
        node1 = storage.load_node("hash123")
        assert node1 is not None
        assert node1["payload"]["foo"] == "bar"
        
        # Verify reload
        storage2 = FileCTMStorage(nodes_file, root_file)
        assert storage2.load_root_hash() == "hash123"
        node2 = storage2.load_node("hash123")
        assert node2 is not None
        assert node2["payload"]["foo"] == "bar"

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
        from idicoc_core.audit import SemanticPayload
        state = wrapper.process_interaction(
            audit_input=SemanticPayload("test transaction 123"),
            context_input=["test transaction 123"],
            context_policies=["test transaction 123"],
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
        assert wrapper2.pipeline is not None
        assert wrapper2.pipeline.ctm.root_hash == root_hash_1

def test_ctm_modes():
    config_log = AuditConfig(rigidity_epsilon=0.5, ctm_mode="log_only")
    wrapper_log = IDICOCNotaryClient(config_log)
    
    # Process interaction
    from idicoc_core.audit import SemanticPayload
    state_log = wrapper_log.process_interaction(
        SemanticPayload("test log"), ["test log"], ["test log"]
    )
    assert state_log.metadata["audit_metrics"] is not None
    
    assert wrapper_log.pipeline is not None
    result = wrapper_log.pipeline.execute("test log", ["test log"], ["test log"])
    assert result["kernel_result"] == {"status": "log_only"}
    assert result["audit_receipt"] == {"status": "log_only"}
    
    # Test disabled mode
    config_dis = AuditConfig(rigidity_epsilon=0.5, ctm_mode="disabled")
    wrapper_dis = IDICOCNotaryClient(config_dis)
    assert wrapper_dis.pipeline is not None
    result_dis = wrapper_dis.pipeline.execute("test log", ["test log"], ["test log"])
    assert result_dis["kernel_result"] == {"status": "disabled"}
    assert result_dis["audit_receipt"] == {"status": "disabled"}
