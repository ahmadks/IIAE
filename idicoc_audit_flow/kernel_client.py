from __future__ import annotations
from typing import Any, Dict, Optional

from idicoc_core.core.custody.merkle_dag import CustodialTraceManager
from idicoc_utils.hashing import canonical_json, sha256_hex


class KernelCustodyClient:
    """Cliente ligero para sellar el resultado del Wrapper en el Merkle DAG del CTM."""

    def __init__(self, ctm: Optional[CustodialTraceManager] = None) -> None:
        self.ctm = ctm or CustodialTraceManager()

    def commit(
        self,
        canonical_state: Any,
        dissonance: float,
        fact_dissonance: float,
        epsilon: float,
        delta_fp: float,
        correction_flag: bool,
        source: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata = metadata or {}
        metadata["mode"] = metadata.get("mode", "factual")
        metadata["epsilon_used"] = metadata.get("epsilon_used", epsilon)

        timestamp = metadata.get("timestamp") if metadata.get("timestamp") else None
        timestamp = timestamp or ""

        invariant_hash = "0" * 64
        property_graph_hash = "0" * 64
        if metadata.get("invariant_state_hash"):
            invariant_hash = metadata["invariant_state_hash"]
        if metadata.get("property_graph_hash"):
            property_graph_hash = metadata["property_graph_hash"]

        payload = {
            "type": "WRAPPER_COMMIT",
            "canonical_state": canonical_state,
            "dissonance": dissonance,
            "fact_dissonance": fact_dissonance,
            "epsilon": epsilon,
            "delta_fp": delta_fp,
            "correction_flag": correction_flag,
            "source": source,
            "metadata": metadata or {},
        }

        node = self.ctm.commit(
            canonical_state,
            dissonance=dissonance,
            epsilon=epsilon,
            property_graph=None,
            timestamp=timestamp,
            invariant_state_hash=invariant_hash,
            property_graph_hash=property_graph_hash,
        )

        return {
            "root_hash": node.node_hash,
            "payload_hash": node.node_hash,
            "payload": payload,
            "timestamp": timestamp,
        }
