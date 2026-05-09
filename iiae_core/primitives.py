import hashlib
import json
from typing import List, Any

def canonical_json(data: Any) -> str:
    """Canonical JSON representation (sorted keys, no whitespace)."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))

def sha256(data: str) -> str:
    """Deterministic SHA-256 hash."""
    return hashlib.sha256(data.encode()).hexdigest()

def merkle_root(leaves: List[str]) -> str:
    """Deterministic Merkle tree root for CTM receipts."""
    if not leaves:
        return sha256("")

    # Sort leaves to ensure deterministic root calculation
    level = [sha256(leaf) for leaf in sorted(leaves)]

    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            next_level.append(sha256(left + right))
        level = next_level

    return level[0]
