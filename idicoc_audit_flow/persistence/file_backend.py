import json
import os
from typing import Dict, List, Any, Optional
from .backend import AEMStorageBackend, CTMStorageBackend

class FileAEMStorage(AEMStorageBackend):
    def __init__(self, filepath: str = "aem_entropy.json"):
        self.filepath = filepath
        self._load()

    def _load(self):
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath, "r") as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {"DISCARDED_NOISE": [], "RECOVERABLE_NOISE": [], "ADMITTED": []}
        else:
            self.data = {"DISCARDED_NOISE": [], "RECOVERABLE_NOISE": [], "ADMITTED": []}

    def _save(self):
        dirpath = os.path.dirname(self.filepath)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath, exist_ok=True)
        with open(self.filepath, "w") as f:
            json.dump(self.data, f, indent=2)

    def save_entropy_event(self, event: Dict[str, Any]) -> None:
        category = event.get("category")
        if category in self.data:
            self.data[category].append(event)
            self._save()

    def load_all_events(self) -> Dict[str, List[Dict[str, Any]]]:
        return self.data

    def clear(self):
        self.data = {"DISCARDED_NOISE": [], "RECOVERABLE_NOISE": [], "ADMITTED": []}
        self._save()

class FileCTMStorage(CTMStorageBackend):
    def __init__(self, nodes_file: str = "ctm_nodes.json", root_file: str = "ctm_root.txt"):
        self.nodes_file = nodes_file
        self.root_file = root_file
        self._load_nodes()
        self._load_root()

    def _load_nodes(self):
        if os.path.exists(self.nodes_file):
            try:
                with open(self.nodes_file, "r") as f:
                    self.nodes = json.load(f)
            except Exception:
                self.nodes = {}
        else:
            self.nodes = {}

    def _save_nodes(self):
        dirpath = os.path.dirname(self.nodes_file)
        if dirpath and not os.path.exists(dirpath):
            os.makedirs(dirpath, exist_ok=True)
        with open(self.nodes_file, "w") as f:
            json.dump(self.nodes, f, indent=2)

    def _load_root(self):
        if os.path.exists(self.root_file):
            try:
                with open(self.root_file, "r") as f:
                    self.root_hash = f.read().strip()
            except Exception:
                self.root_hash = None
        else:
            self.root_hash = None

    def _save_root(self):
        if self.root_hash:
            dirpath = os.path.dirname(self.root_file)
            if dirpath and not os.path.exists(dirpath):
                os.makedirs(dirpath, exist_ok=True)
            with open(self.root_file, "w") as f:
                f.write(self.root_hash)
        elif os.path.exists(self.root_file):
            try:
                os.remove(self.root_file)
            except Exception:
                pass

    def save_node(self, node_hash: str, node_data: Dict[str, Any]) -> None:
        self.nodes[node_hash] = node_data
        self._save_nodes()

    def load_node(self, node_hash: str) -> Optional[Dict[str, Any]]:
        return self.nodes.get(node_hash)

    def load_all_nodes(self) -> Dict[str, Dict[str, Any]]:
        return self.nodes

    def save_root_hash(self, root_hash: str) -> None:
        self.root_hash = root_hash
        self._save_root()

    def load_root_hash(self) -> Optional[str]:
        return self.root_hash
