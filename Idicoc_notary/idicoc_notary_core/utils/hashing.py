import hmac
import hashlib
import json
from typing import Any
import numpy as np

class NumpyEncoder(json.JSONEncoder):
    """Custom encoder for NumPy data types."""
    def default(self, o: Any) -> Any:
        if isinstance(o, np.ndarray):
            return o.tolist()
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.bool_):
            return bool(o)
        # Handle custom objects with to_dict or dict representations if needed
        if hasattr(o, "__dict__"):
            return o.__dict__
        return super().default(o)

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

    return hmac.new(key.encode("utf-8"), data.encode("utf-8"), hashlib.sha256).hexdigest()