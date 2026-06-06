# idicoc_core/ctm/merkle_dag.py
from __future__ import annotations
import os
import json
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Protocol

try:
    import fcntl
except ImportError:
    fcntl = None

from idicoc_core.utils.hashing import (
    canonical_json,
    hmac_sha256_hex,
    sha256_dict,
    sha256_hex,
)
from idicoc_core.exceptions import DataCorruptionError, PersistenceError
from idicoc_core.api.schemas import SessionContext


class HardwareSealer(Protocol):
    def seal(self, payload: Dict[str, Any]) -> Dict[str, Any]: ...


class CTMStorageBackend(Protocol):
    def save_node(self, node_hash: str, node_data: Dict[str, Any]) -> None: ...
    def load_node(self, node_hash: str) -> Optional[Dict[str, Any]]: ...
    def load_all_nodes(self) -> Dict[str, Dict[str, Any]]: ...
    def save_root_hash(self, root_hash: str) -> None: ...
    def load_root_hash(self) -> Optional[str]: ...


class NoOpHardwareSealer:
    def seal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return payload


class EnvHardwareSealer:
    def __init__(self, key_env: str = "IIAE_HARDWARE_KEY", require_key: bool = False):
        self.key_env = key_env
        self.require_key = require_key
        self.key = os.environ.get(key_env)

        if self.require_key and not self.key:
            raise RuntimeError(
                f"Se requiere la variable de entorno de hardware '{key_env}' para el sellado."
            )

    def seal(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.key:
            if self.require_key:
                raise RuntimeError(
                    f"Se intentó sellar con hardware pero no se encontró la clave en '{self.key_env}'."
                )
            return payload

        import copy
        payload_copy = copy.deepcopy(payload)
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
    invariant_state_hash: Optional[str] = None
    property_graph_hash: Optional[str] = None
    deviation_score: Optional[float] = None
    correction_flag: Optional[bool] = None
    hss_anchor: Optional[str] = None
    epuf_anchor: Optional[str] = None


class MerkleDAG:
    def __init__(
        self,
        sealer: Optional[HardwareSealer] = None,
        storage_backend: Optional[CTMStorageBackend] = None,
    ):
        self._nodes: Dict[str, MerkleNode] = {}
        self._root_hash: Optional[str] = None
        self._sealer: HardwareSealer = sealer or NoOpHardwareSealer()
        self._storage = storage_backend

        if self._storage is not None:
            self._root_hash = self._storage.load_root_hash()

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
        parent_hashes = (
            parent_hashes
            if parent_hashes is not None
            else ([self._root_hash] if self._root_hash else [])
        )

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

        if self._storage is not None:
            self._storage.save_node(node_hash, asdict(node))
            self._storage.save_root_hash(node_hash)

        return node

    def get_node(self, node_hash: str) -> Optional[MerkleNode]:
        if node_hash in self._nodes:
            return self._nodes[node_hash]

        if self._storage is None:
            return None

        node_data = self._storage.load_node(node_hash)
        if node_data is None:
            return None

        node = MerkleNode(
            node_hash=node_data["node_hash"],
            parent_hashes=node_data["parent_hashes"],
            timestamp=node_data["timestamp"],
            payload=node_data["payload"],
            hardware_evidence=node_data.get("hardware_evidence"),
            invariant_state_hash=node_data.get("invariant_state_hash"),
            property_graph_hash=node_data.get("property_graph_hash"),
            deviation_score=node_data.get("deviation_score"),
            correction_flag=node_data.get("correction_flag"),
            hss_anchor=node_data.get("hss_anchor"),
            epuf_anchor=node_data.get("epuf_anchor"),
        )
        self._nodes[node_hash] = node
        return node

    def create_genesis(self, metadata: Dict[str, Any], timestamp: str) -> MerkleNode:
        payload = {
            "type": "GENESIS",
            "stage": "CTM",
            "timestamp": timestamp,
            "metadata": metadata,
        }
        return self.append(payload, timestamp=timestamp, parent_hashes=[])

    def to_dict(self) -> Dict[str, Any]:
        nodes_dict: Dict[str, Dict[str, Any]]
        if self._storage is not None:
            nodes_dict = self._storage.load_all_nodes()
        else:
            nodes_dict = {h: asdict(n) for h, n in self._nodes.items()}

        return {
            "root_hash": self._root_hash,
            "nodes": nodes_dict,
        }


class CustodialTraceManager:
    def __init__(
        self,
        dag: Optional[MerkleDAG] = None,
        storage_backend: Optional[CTMStorageBackend] = None,
        zkp_mode: bool = False,
    ):
        self._dag = dag or MerkleDAG(storage_backend=storage_backend)
        self.zkp_mode = zkp_mode

    def _hash_commitment(self, obj: Any) -> str:
        serialized = self._safe_serialize(obj)
        try:
            return sha256_hex(canonical_json(serialized))
        except Exception:
            return sha256_hex(str(serialized))

    @property
    def root_hash(self) -> Optional[str]:
        return self._dag.root_hash

    def initialize_genesis(self, metadata: Dict[str, Any], timestamp: str) -> Optional[MerkleNode]:
        if self._dag.root_hash:
            return self._dag.get_node(self._dag.root_hash)
        return self._dag.create_genesis(metadata=metadata, timestamp=timestamp)

    @staticmethod
    def _strip_distribution(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: CustodialTraceManager._strip_distribution(v) for k, v in obj.items() if k != "distribution"}
        if isinstance(obj, list):
            return [CustodialTraceManager._strip_distribution(v) for v in obj]
        return obj

    def commit(
        self,
        canonical_state: Any,
        timestamp: str,
        dissonance: float = 0.0,
        epsilon: float = 0.0,
        property_graph: Any = None,
        invariant_state_hash: Optional[str] = None,
        property_graph_hash: Optional[str] = None,
        aem_counters: Optional[Dict[str, int]] = None,
        transaction_id: Optional[str] = None,
        violations: Optional[List[str]] = None,
        dissonance_components: Optional[Dict[str, float]] = None,
    ) -> MerkleNode:
        pg_val = getattr(property_graph, "nodes", property_graph)
        
        # Compute canonical state hash (includes distribution vector if present)
        cs_hash = invariant_state_hash or self._hash_commitment(canonical_state)
        pg_hash = property_graph_hash or self._hash_commitment(pg_val)

        if self.zkp_mode:
            cs_payload = cs_hash
            pg_payload = pg_hash
        else:
            # Build lightweight forensic fingerprint instead of serializing the full state
            import math
            from datetime import datetime, timezone
            integrity_score = max(0.0, 1.0 - dissonance)
            if math.isinf(dissonance) or math.isnan(dissonance):
                integrity_score = 0.0

            cs_payload = {
                "transaction_id": transaction_id or f"tx_{int(datetime.now(timezone.utc).timestamp())}",
                "integrity_score": integrity_score,
                "canonical_state_hash": cs_hash,
                "violated_policies": violations or [],
                "is_admitted": float(dissonance) <= float(epsilon) if not (math.isinf(dissonance) or math.isnan(dissonance)) else False
            }
            if dissonance_components is not None:
                cs_payload["dissonance_components"] = dissonance_components
            # Strip distribution from property graph as well
            pg_payload = self._strip_distribution(self._safe_serialize(pg_val))

        logical_payload = {
            "type": "COMMIT",
            "stage": "CTM",
            "timestamp": timestamp,
            "canonical_state": cs_payload,
            "dissonance": dissonance,
            "epsilon": epsilon,
            "property_graph": pg_payload,
        }
        if aem_counters is not None:
            logical_payload["aem_counters"] = aem_counters

        return self._dag.append(
            logical_payload,
            timestamp=timestamp,
            invariant_state_hash=cs_hash,
            property_graph_hash=pg_hash,
            deviation_score=dissonance,
            correction_flag=False,
        )

    def commit_trace(
        self,
        context: SessionContext | Dict[str, Any],
        output: str,
        d_s: float,
        is_admitted: bool,
        violations: List[str],
        transaction_id: Optional[str] = None,
        timestamp: Optional[str] = None,
        dissonance_components: Optional[Dict[str, float]] = None,
    ) -> None:
        """
        Commit a trace to the cryptographic Merkle DAG.
        This represents the forensic immutable trace logging.
        """
        from datetime import datetime, timezone
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat()

        if isinstance(context, dict):
            user_prompt = context.get("user_prompt", "")
            rag_context = context.get("rag_context", "")
            metadata = context.get("metadata", {})
            dist_val = context.get("distribution") or metadata.get("distribution")
        else:
            user_prompt = context.user_prompt
            rag_context = context.rag_context
            metadata = context.metadata or {}
            dist_val = getattr(context, "distribution", None) or metadata.get("distribution")

        logical_payload = {
            "user_prompt": user_prompt,
            "rag_context": rag_context,
            "output": output,
            "dissonance": d_s,
            "is_admitted": is_admitted,
            "violations": violations,
            "timestamp": timestamp
        }

        # Extract/Include distribution vector if present for the full state hash
        if dist_val is None:
            try:
                if isinstance(output, str) and (output.startswith("[") or "array" in output):
                    import ast
                    parsed = ast.literal_eval(output)
                    if isinstance(parsed, (list, tuple)):
                        dist_val = list(parsed)
            except Exception:
                pass

        if dist_val is not None:
            if hasattr(dist_val, "tolist"):
                dist_val = dist_val.tolist()
            logical_payload["distribution"] = dist_val

        invariant_state_hash = sha256_hex(canonical_json(logical_payload))

        if dissonance_components is None:
            dissonance_components = {
                "d_axiomatic": d_s,
                "d_context": 0.0
            }
            if isinstance(context, dict):
                metrics = context.get("metrics") or context.get("metadata", {}).get("audit_metrics")
            else:
                metrics = getattr(context, "metrics", None) or (context.metadata or {}).get("audit_metrics")
            
            if isinstance(metrics, dict):
                dissonance_components["d_context"] = float(metrics.get("d_context", 0.0))
                dissonance_components["d_axiomatic"] = float(metrics.get("d_logic", metrics.get("d_2", d_s)))

        if is_admitted:
            self.commit(
                canonical_state=logical_payload,
                timestamp=timestamp,
                dissonance=d_s,
                invariant_state_hash=invariant_state_hash,
                transaction_id=transaction_id,
                violations=violations,
                dissonance_components=dissonance_components
            )
        else:
            self.seal_failure(
                snapshot=logical_payload,
                timestamp=timestamp,
                transaction_id=transaction_id,
                violations=violations,
                dissonance_components=dissonance_components
            )

    def seal_failure(
        self,
        snapshot: Dict[str, Any],
        timestamp: str,
        transaction_id: Optional[str] = None,
        violations: Optional[List[str]] = None,
        dissonance_components: Optional[Dict[str, float]] = None,
    ) -> MerkleNode:
        # Calculate full hash first
        snapshot_hash = self._hash_commitment(snapshot)

        if self.zkp_mode:
            snapshot_payload = snapshot_hash
        else:
            # Build lightweight forensic fingerprint instead of serializing the full state
            from datetime import datetime, timezone
            snapshot_payload = {
                "transaction_id": transaction_id or f"tx_{int(datetime.now(timezone.utc).timestamp())}",
                "integrity_score": 0.0,
                "canonical_state_hash": snapshot_hash,
                "violated_policies": violations or snapshot.get("violations") or [],
                "is_admitted": False
            }
            if dissonance_components is not None:
                snapshot_payload["dissonance_components"] = dissonance_components

        logical_payload = {
            "type": "FAILURE",
            "stage": "CTM",
            "timestamp": timestamp,
            "snapshot": snapshot_payload,
        }
        return self._dag.append(
            logical_payload,
            timestamp=timestamp,
            deviation_score=1.0,
            correction_flag=True,
        )

    def get_node(self, node_hash: str) -> Optional[MerkleNode]:
        return self._dag.get_node(node_hash)

    def get_last_failure_snapshot(self, root_hash: str) -> Dict[str, Any]:
        node = self.get_node(root_hash)
        if node is None:
            raise RuntimeError(f"Root hash {root_hash} no encontrado en el DAG.")

        if node.payload.get("type") != "FAILURE":
            raise RuntimeError(
                f"El nodo {root_hash} no es de tipo FAILURE. Recuperación imposible."
            )

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
            "policy_hashes": self._extract_policy_hashes(node.payload),
            "dissonance": node.payload.get("payload", {}).get("dissonance"),
            "epsilon": node.payload.get("payload", {}).get("epsilon"),
            "invariant_state_hash": node.invariant_state_hash,
            "property_graph_hash": node.property_graph_hash,
            "hardware_evidence": node.hardware_evidence,
        }

    @staticmethod
    def _extract_policy_hashes(payload: Dict[str, Any]) -> list[str]:
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


# File backend persistence helpers (merged for DDD packaging)
def _ensure_parent_dir(filepath: str) -> None:
    directory = os.path.dirname(filepath)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def _atomic_write_json(filepath: str, payload: Any) -> None:
    _ensure_parent_dir(filepath)
    tmp_path = f"{filepath}.tmp"
    with open(filepath, "a+", encoding="utf-8") as lock_handle:
        if fcntl is not None:
            try:
                fcntl.flock(lock_handle, fcntl.LOCK_EX)
            except OSError as exc:
                raise PersistenceError(f"No se pudo adquirir bloqueo exclusivo para {filepath}: {exc}")
        try:
            with open(tmp_path, "w", encoding="utf-8") as tmp_handle:
                json.dump(payload, tmp_handle, indent=2, sort_keys=True)
                tmp_handle.flush()
                os.fsync(tmp_handle.fileno())
            os.replace(tmp_path, filepath)
        finally:
            if fcntl is not None:
                fcntl.flock(lock_handle, fcntl.LOCK_UN)


def _atomic_write_text(filepath: str, value: str) -> None:
    _ensure_parent_dir(filepath)
    tmp_path = f"{filepath}.tmp"
    with open(filepath, "a+", encoding="utf-8") as lock_handle:
        if fcntl is not None:
            try:
                fcntl.flock(lock_handle, fcntl.LOCK_EX)
            except OSError as exc:
                raise PersistenceError(f"No se pudo adquirir bloqueo exclusivo para {filepath}: {exc}")
        try:
            with open(tmp_path, "w", encoding="utf-8") as tmp_handle:
                tmp_handle.write(value)
                tmp_handle.flush()
                os.fsync(tmp_handle.fileno())
            os.replace(tmp_path, filepath)
        finally:
            if fcntl is not None:
                fcntl.flock(lock_handle, fcntl.LOCK_UN)


def _load_json_locked(filepath: str) -> Any:
    if not os.path.exists(filepath):
        raise FileNotFoundError(filepath)

    with open(filepath, "r", encoding="utf-8") as handle:
        if fcntl is not None:
            try:
                fcntl.flock(handle, fcntl.LOCK_SH)
            except OSError as exc:
                raise PersistenceError(f"No se pudo adquirir bloqueo compartido para {filepath}: {exc}")
        try:
            return json.load(handle)
        except json.JSONDecodeError as exc:
            raise DataCorruptionError(filepath, str(exc))
        finally:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _load_text_locked(filepath: str) -> str:
    if not os.path.exists(filepath):
        raise FileNotFoundError(filepath)

    with open(filepath, "r", encoding="utf-8") as handle:
        if fcntl is not None:
            try:
                fcntl.flock(handle, fcntl.LOCK_SH)
            except OSError as exc:
                raise PersistenceError(f"No se pudo adquirir bloqueo compartido para {filepath}: {exc}")
        try:
            return handle.read().strip()
        finally:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _iter_nodes_file(nodes_file: str) -> Generator[Dict[str, Any], None, None]:
    if not os.path.exists(nodes_file):
        return

    with open(nodes_file, "r", encoding="utf-8") as handle:
        if fcntl is not None:
            try:
                fcntl.flock(handle, fcntl.LOCK_SH)
            except OSError as exc:
                raise PersistenceError(f"No se pudo adquirir bloqueo compartido para {nodes_file}: {exc}")
        try:
            for line_number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError as exc:
                    raise DataCorruptionError(
                        nodes_file,
                        f"Línea {line_number} inválida: {exc}",
                    )
        finally:
            if fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)


def _load_nodes_map_if_available(nodes_file: str) -> Optional[Dict[str, Dict[str, Any]]]:
    try:
        raw = _load_json_locked(nodes_file)
    except FileNotFoundError:
        return {}
    except DataCorruptionError:
        return None

    if isinstance(raw, dict) and all(isinstance(value, dict) for value in raw.values()):
        return raw
    return None


class FileCTMStorage(CTMStorageBackend):
    def __init__(self, nodes_file: str = "ctm_nodes.json", root_file: str = "ctm_root.txt"):
        self.nodes_file = nodes_file
        self.root_file = root_file
        self.root_hash: Optional[str] = None
        self._load_root()

    def _load_root(self) -> None:
        if not os.path.exists(self.root_file):
            self.root_hash = None
            return

        self.root_hash = _load_text_locked(self.root_file)

    def _save_root(self) -> None:
        if self.root_hash:
            _atomic_write_text(self.root_file, self.root_hash)
        elif os.path.exists(self.root_file):
            _ensure_parent_dir(self.root_file)
            with open(self.root_file, "a+", encoding="utf-8") as lock_handle:
                if fcntl is not None:
                    try:
                        fcntl.flock(lock_handle, fcntl.LOCK_EX)
                    except OSError as exc:
                        raise PersistenceError(f"No se pudo adquirir bloqueo exclusivo para {self.root_file}: {exc}")
                try:
                    os.remove(self.root_file)
                finally:
                    if fcntl is not None:
                        fcntl.flock(lock_handle, fcntl.LOCK_UN)

    def save_node(self, node_hash: str, node_data: Dict[str, Any]) -> None:
        if not isinstance(node_data, dict):
            raise ValueError("La información del nodo debe ser un diccionario.")

        _ensure_parent_dir(self.nodes_file)
        serialized = json.dumps(node_data, sort_keys=True)
        with open(self.nodes_file, "a+", encoding="utf-8") as lock_handle:
            if fcntl is not None:
                try:
                    fcntl.flock(lock_handle, fcntl.LOCK_EX)
                except OSError as exc:
                    raise PersistenceError(f"No se pudo adquirir bloqueo exclusivo para {self.nodes_file}: {exc}")
            try:
                lock_handle.write(serialized + "\n")
                lock_handle.flush()
                os.fsync(lock_handle.fileno())
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_handle, fcntl.LOCK_UN)

    def load_node(self, node_hash: str) -> Optional[Dict[str, Any]]:
        nodes_map = _load_nodes_map_if_available(self.nodes_file)
        if nodes_map is not None:
            return nodes_map.get(node_hash)

        for node in _iter_nodes_file(self.nodes_file):
            if node.get("node_hash") == node_hash:
                return node
        return None

    def load_all_nodes(self) -> Dict[str, Dict[str, Any]]:
        nodes_map = _load_nodes_map_if_available(self.nodes_file)
        if nodes_map is not None:
            return nodes_map

        nodes: Dict[str, Dict[str, Any]] = {}
        for node in _iter_nodes_file(self.nodes_file):
            node_hash = node.get("node_hash")
            if node_hash:
                nodes[node_hash] = node
        return nodes

    def save_root_hash(self, root_hash: str) -> None:
        self.root_hash = root_hash
        self._save_root()

    def load_root_hash(self) -> Optional[str]:
        return self.root_hash
