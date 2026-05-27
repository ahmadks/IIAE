from __future__ import annotations

import fcntl
import json
import os
from typing import Any, Dict, Generator, List, Optional

from .backend import CTMStorageBackend
from idicoc_notary_core.audit.exceptions import DataCorruptionError, PersistenceError


def _ensure_parent_dir(filepath: str) -> None:
    directory = os.path.dirname(filepath)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)


def _atomic_write_json(filepath: str, payload: Any) -> None:
    _ensure_parent_dir(filepath)
    tmp_path = f"{filepath}.tmp"
    with open(filepath, "a+", encoding="utf-8") as lock_handle:
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
            fcntl.flock(lock_handle, fcntl.LOCK_UN)


def _atomic_write_text(filepath: str, value: str) -> None:
    _ensure_parent_dir(filepath)
    tmp_path = f"{filepath}.tmp"
    with open(filepath, "a+", encoding="utf-8") as lock_handle:
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
            fcntl.flock(lock_handle, fcntl.LOCK_UN)


def _load_json_locked(filepath: str) -> Any:
    if not os.path.exists(filepath):
        raise FileNotFoundError(filepath)

    with open(filepath, "r", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH)
        except OSError as exc:
            raise PersistenceError(f"No se pudo adquirir bloqueo compartido para {filepath}: {exc}")
        try:
            return json.load(handle)
        except json.JSONDecodeError as exc:
            raise DataCorruptionError(filepath, str(exc))
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _load_text_locked(filepath: str) -> str:
    if not os.path.exists(filepath):
        raise FileNotFoundError(filepath)

    with open(filepath, "r", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH)
        except OSError as exc:
            raise PersistenceError(f"No se pudo adquirir bloqueo compartido para {filepath}: {exc}")
        try:
            return handle.read().strip()
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _iter_nodes_file(nodes_file: str) -> Generator[Dict[str, Any], None, None]:
    if not os.path.exists(nodes_file):
        return

    with open(nodes_file, "r", encoding="utf-8") as handle:
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
                try:
                    fcntl.flock(lock_handle, fcntl.LOCK_EX)
                except OSError as exc:
                    raise PersistenceError(f"No se pudo adquirir bloqueo exclusivo para {self.root_file}: {exc}")
                try:
                    os.remove(self.root_file)
                finally:
                    fcntl.flock(lock_handle, fcntl.LOCK_UN)

    def save_node(self, node_hash: str, node_data: Dict[str, Any]) -> None:
        if not isinstance(node_data, dict):
            raise ValueError("La información del nodo debe ser un diccionario.")

        _ensure_parent_dir(self.nodes_file)
        serialized = json.dumps(node_data, sort_keys=True)
        with open(self.nodes_file, "a+", encoding="utf-8") as lock_handle:
            try:
                fcntl.flock(lock_handle, fcntl.LOCK_EX)
            except OSError as exc:
                raise PersistenceError(f"No se pudo adquirir bloqueo exclusivo para {self.nodes_file}: {exc}")
            try:
                lock_handle.write(serialized + "\n")
                lock_handle.flush()
                os.fsync(lock_handle.fileno())
            finally:
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
