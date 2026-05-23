"""
Hashing utilities for deterministic operations.
"""

import hashlib
import json
from typing import Any


def canonical_json(data: Any) -> str:
    """
    Convert data to canonical JSON (sorted keys, no whitespace).

    Ensures same input always produces same hash (deterministic).
    """

    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(data: str) -> str:
    """Compute SHA-256 hash of string, return as hex."""

    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def sha256_dict(data: dict) -> str:
    """Compute SHA-256 hash of dict (canonical JSON)."""

    return sha256_hex(canonical_json(data))


def hmac_sha256_hex(key: str, data: str) -> str:
    """Compute an HMAC-SHA256 signature over a string, return as hex."""

    return hashlib.new("sha256", data.encode("utf-8"), key.encode("utf-8")).hexdigest()