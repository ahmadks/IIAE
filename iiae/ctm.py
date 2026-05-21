import hashlib
import json
from datetime import datetime, timezone

CTM_VERSION = "1.0.0"

def generate_merkle_root(axioms: list, salt: str = None) -> str:
    """
    Computes a deterministic Merkle root hash for the session axioms.
    Mixes an optional salt to prevent collision attacks.
    """
    _salt = salt or ""
    
    if not axioms:
        return hashlib.sha256((b"empty_manifold" + _salt.encode('utf-8'))).hexdigest()
    
    hashes = [hashlib.sha256((str(ax) + _salt).encode('utf-8')).hexdigest() for ax in axioms]
    
    while len(hashes) > 1:
        if len(hashes) % 2 != 0:
            hashes.append(hashes[-1])
        next_level = []
        for i in range(0, len(hashes), 2):
            combined = hashes[i] + hashes[i+1]
            next_level.append(hashlib.sha256((combined + _salt).encode('utf-8')).hexdigest())
        hashes = next_level
        
    return hashes[0]

def _hash_payload(payload: dict) -> str:
    data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def create_receipt(prompt: str, response: str, ds: float, axioms: list, model_id: str, salt: str = None) -> dict:
    """
    Seals the sub-symbolic state transition matrix within a cryptographic CTM ledger block.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    merkle_root = generate_merkle_root(axioms, salt=salt)
    
    # Structural Payload Binding
    payload = {
        "version": CTM_VERSION,
        "model_id": model_id,
        "timestamp": timestamp,
        "ds": float(ds),
        "axioms_count": len(axioms),
        "merkle_root": merkle_root,
        "prompt_hash": hashlib.sha256(prompt.encode('utf-8')).hexdigest(),
        "response_hash": hashlib.sha256(response.encode('utf-8')).hexdigest()
    }
    
    ctm_seal = _hash_payload(payload)
    
    return {
        "payload": payload,
        "ctm_seal": ctm_seal,
        "axioms": axioms
    }

def verify_receipt(receipt: dict, salt: str = None) -> bool:
    """
    Verifies the physical-cryptographic alignment of a sealed state block.
    """
    try:
        payload = receipt.get("payload", {})
        ctm_seal = receipt.get("ctm_seal", "")
        axioms = receipt.get("axioms", [])
        
        # Verify Invariance Corridor Merkle integrity
        current_merkle = generate_merkle_root(axioms, salt=salt)
        if current_merkle != payload.get("merkle_root"):
            return False
            
        # Re-compute and verify structural signature block
        computed_seal = _hash_payload(payload)
        
        return computed_seal == ctm_seal
    except Exception:
        return False
