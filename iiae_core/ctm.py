import time
import uuid
from typing import List, Dict, Any
from .primitives import sha256, merkle_root, canonical_json

class CTM_Module:
    """
    Custodial Traceability Module (CTM)
    Implements the 7-stage IDICOC (Invariant Data Integrity Chain-of-Custody) protocol.
    Persists events in a Merkle DAG Ledger.
    """
    def __init__(self):
        self.ledger = []
        self.root_hash = None

    def seal(self, task_id: str, stage: str, input_state: Any, output_state: Any, ds: float, epsilon: float) -> Dict[str, Any]:
        """
        Executes a cryptographic seal for a state transition.
        Generates a 'Receipt of Reasoning' (RoR).
        """
        timestamp = time.time()
        
        # Payload for the Merkle Node
        payload = {
            "task_id": task_id,
            "stage": stage,
            "input_hash": sha256(canonical_json(input_state)),
            "output_hash": sha256(canonical_json(output_state)),
            "ds": ds,
            "epsilon": epsilon,
            "timestamp": timestamp
        }
        
        # Node metadata
        node = {
            "event_id": str(uuid.uuid4()),
            "payload": payload,
            "parent_hash": self.root_hash,
            "node_hash": sha256(canonical_json(payload) + str(self.root_hash))
        }
        
        # Update Ledger and Root Hash
        self.ledger.append(node)
        
        # For simplicity, Merkle Root is recomputed from the leaf hashes of the ledger
        leaves = [n["node_hash"] for n in self.ledger]
        self.root_hash = merkle_root(leaves)
        
        # Forensic Receipt (RoR)
        receipt = {
            "merkle_root": self.root_hash,
            "node_hash": node["node_hash"],
            "trace_id": node["event_id"],
            "timestamp": timestamp,
            "integrity_status": "DETERMINISTIC_PASS" if ds <= epsilon else "INTEGRITY_FAILURE"
        }
        
        return receipt

    def get_ledger(self) -> List[dict]:
        return self.ledger
