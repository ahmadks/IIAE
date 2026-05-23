# idicoc_core/core/custody/merkle_dag.py
from __future__ import annotations
import os
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Protocol

from idicoc_utils.hashing import (
    canonical_json,
    hmac_sha256_hex,
    sha256_dict,
)


class HardwareSealer(Protocol):
    def seal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ...


class NoOpHardwareSealer:
    def seal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return payload


class EnvHardwareSealer:
    def __init__(self, key_env: str = "IIAE_HARDWARE_KEY"):
        self.key = os.environ.get(key_env)

    def seal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.key:
            return payload
        payload_copy = dict(payload)
        serialized = canonical_json(payload)
        signature = hmac_sha256_hex(self.key, serialized)
        payload_copy["hardware_evidence"] = {
            "type": "HMAC_ENV_SEAL",
            "signature": signature,
        }
        return payload_copy


@dataclass
class MerkleNode:
    node_hash: str
    parent_hashes: List[str]
    timestamp: str
    payload: Dict[str, Any]
    hardware_evidence: Optional[Dict[str, Any]] = None
    # Campos extendidos del Anexo K
    invariant_state_hash: Optional[str] = None
    property_graph_hash: Optional[str] = None
    deviation_score: Optional[float] = None
    correction_flag: Optional[bool] = None
    hss_anchor: Optional[str] = None
    epuf_anchor: Optional[str] = None


class MerkleDAG:
    def __init__(self, sealer: Optional[HardwareSealer] = None):
        self._nodes: Dict[str, MerkleNode] = {}
        self._root_hash: Optional[str] = None
        self._sealer: HardwareSealer = sealer or NoOpHardwareSealer()

    @property
    def root_hash(self) -> Optional[str]:
        return self._root_hash

    @property
    def nodes(self) -> Dict[str, MerkleNode]:
        return self._nodes

    def _build_payload(
        self,
        logical_payload: Dict[str, Any],
        parent_hashes: List[str],
        timestamp: str,
    ) -> Dict[str, Any]:
        base = {
            "parent_hashes": parent_hashes,
            "timestamp": timestamp,
            "payload": logical_payload,
        }
        base["node_hash_pre_seal"] = sha256_dict(base)
        sealed = self._sealer.seal(base)
        return sealed

    def append(
        self,
        logical_payload: Dict[str, Any],
        timestamp: str,
        parent_hashes: Optional[List[str]] = None,
        invariant_state_hash: Optional[str] = None,
        property_graph_hash: Optional[str] = None,
        deviation_score: Optional[float] = None,
        correction_flag: Optional[bool] = None,
    ) -> MerkleNode:
        """
        Append determinista con metadatos extendidos del Anexo K.
        """
        parent_hashes = parent_hashes if parent_hashes is not None else ([self._root_hash] if self._root_hash else [])

        sealed_payload = self._build_payload(
            logical_payload=logical_payload,
            parent_hashes=parent_hashes,
            timestamp=timestamp,
        )

        node_hash = sha256_dict(sealed_payload)

        node = MerkleNode(
            node_hash=node_hash,
            parent_hashes=parent_hashes,
            timestamp=timestamp,
            payload=sealed_payload,
            hardware_evidence=sealed_payload.get("hardware_evidence"),
            invariant_state_hash=invariant_state_hash,
            property_graph_hash=property_graph_hash,
            deviation_score=deviation_score,
            correction_flag=correction_flag,
        )

        self._nodes[node_hash] = node
        self._root_hash = node_hash
        return node

    def get_node(self, node_hash: str) -> Optional[MerkleNode]:
        return self._nodes.get(node_hash)

    def create_genesis(self, metadata: Dict[str, Any], timestamp: str) -> MerkleNode:
        payload = {
            "type": "GENESIS",
            "stage": "CTM",
            "timestamp": timestamp,
            "metadata": metadata,
        }
        return self.append(payload, timestamp=timestamp, parent_hashes=[])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_hash": self._root_hash,
            "nodes": {h: asdict(n) for h, n in self._nodes.items()},
        }


class CustodialTraceManager:
    def __init__(self, dag: Optional[MerkleDAG] = None):
        self._dag = dag or MerkleDAG()

    @property
    def root_hash(self) -> Optional[str]:
        return self._dag.root_hash

    def initialize_genesis(self, metadata: Dict[str, Any], timestamp: str) -> MerkleNode:
        return self._dag.create_genesis(metadata=metadata, timestamp=timestamp)

    def commit(
        self,
        canonical_state: Any,
        timestamp: str,
        dissonance: float = 0.0,
        epsilon: float = 0.0,
        property_graph: Any = None,
        invariant_state_hash: Optional[str] = None,
        property_graph_hash: Optional[str] = None,
    ) -> MerkleNode:
        logical_payload = {
            "type": "COMMIT",
            "stage": "CTM",
            "timestamp": timestamp,
            "canonical_state": self._safe_serialize(canonical_state),
            "dissonance": dissonance,
            "epsilon": epsilon,
            "property_graph": self._safe_serialize(getattr(property_graph, "nodes", property_graph)),
        }
        return self._dag.append(
            logical_payload,
            timestamp=timestamp,
            invariant_state_hash=invariant_state_hash,
            property_graph_hash=property_graph_hash,
            deviation_score=dissonance,
            correction_flag=False,
        )

    def seal_failure(self, snapshot: Dict[str, Any], timestamp: str) -> MerkleNode:
        logical_payload = {
            "type": "FAILURE",
            "stage": "CTM",
            "timestamp": timestamp,
            "snapshot": self._safe_serialize(snapshot),
        }
        return self._dag.append(logical_payload, timestamp=timestamp)

    def get_node(self, node_hash: str) -> Optional[MerkleNode]:
        return self._dag.get_node(node_hash)

    def get_last_failure_snapshot(self, root_hash: str) -> Dict[str, Any]:
        node = self.get_node(root_hash)
        if node is None:
            raise RuntimeError(f"Root hash {root_hash} no encontrado en el DAG.")

        if node.payload.get("type") != "FAILURE":
            raise RuntimeError(f"El nodo {root_hash} no es de tipo FAILURE. Recuperación imposible.")

        snapshot = node.payload.get("snapshot")
        if not snapshot:
            raise RuntimeError("Estructura de snapshot corrompida: falta el objeto 'snapshot'.")

        return snapshot

    def export_dag(self) -> Dict[str, Any]:
        return self._dag.to_dict()

    def export_receipt(self, node_hash: str) -> Dict[str, Any]:
        node = self.get_node(node_hash)
        if node is None:
            raise RuntimeError(f"Nodo {node_hash} no encontrado en el DAG.")

        return {
            "node_hash": node.node_hash,
            "parent_hashes": node.parent_hashes,
            "timestamp": node.timestamp,
            "canonical_state": node.payload.get("payload", {}).get("canonical_state"),
            "axiom_hashes": self._extract_axiom_hashes(node.payload),
            "dissonance": node.payload.get("payload", {}).get("dissonance"),
            "epsilon": node.payload.get("payload", {}).get("epsilon"),
            "invariant_state_hash": node.invariant_state_hash,
            "property_graph_hash": node.property_graph_hash,
            "hardware_evidence": node.hardware_evidence,
        }

    @staticmethod
    def _extract_axiom_hashes(payload: Dict[str, Any]) -> list[str]:
        payload_body = payload.get("payload", {})
        if not isinstance(payload_body, dict):
            return []
        graph = payload_body.get("property_graph")
        if isinstance(graph, dict):
            return list(graph.keys())
        return []

    @staticmethod
    def _safe_serialize(obj: Any) -> Any:
        try:
            canonical_json(obj)
            return obj
        except Exception:
            return {"__repr__": repr(obj)}
