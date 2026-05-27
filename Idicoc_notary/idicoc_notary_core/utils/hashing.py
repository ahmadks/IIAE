"""
Hashing utilities for deterministic operations.
"""

import hashlib
import json
from typing import Any
import numpy as np

class NumpyEncoder(json.JSONEncoder):
    """Custom encoder for NumPy data types."""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.bool_):
            return bool(obj)
        # Handle custom objects with to_dict or dict representations if needed
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)

def canonical_json(data: Any) -> str:
    """
    Convert data to canonical JSON (sorted keys, no whitespace).

    Ensures same input always produces same hash (deterministic).
    Handles NumPy arrays and types automatically.
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, cls=NumpyEncoder)


def sha256_hex(data: str) -> str:
    """Compute SHA-256 hash of string, return as hex."""

    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def sha256_dict(data: dict) -> str:
    """Compute SHA-256 hash of dict (canonical JSON)."""

    return sha256_hex(canonical_json(data))


def hmac_sha256_hex(key: str, data: str) -> str:
    """Compute an HMAC-SHA256 signature over a string, return as hex."""

    return hashlib.new("sha256", data.encode("utf-8"), key.encode("utf-8")).hexdigest()