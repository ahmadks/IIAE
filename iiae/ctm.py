import hashlib
import time
import json

def create_receipt(prompt: str, response: str, ds: float, axioms: list, model_id: str, parent_hash: str = None, session_id: str = None) -> dict:
    """
    Creates a deterministic cryptographic seal for the interaction.
    """
    data = {
        "prompt": prompt,
        "response": response,
        "ds": ds,
        "axioms": axioms,
        "model_id": model_id,
        "timestamp": time.time(),
        "parent_hash": parent_hash,
        "session_id": session_id
    }
    canonical = json.dumps(data, sort_keys=True)
    seal = hashlib.sha256(canonical.encode()).hexdigest()
    return {
        "data": data,
        "ctm_seal": seal
    }

def verify_receipt(receipt: dict) -> bool:
    """
    Verifies the integrity of a receipt using its seal.
    """
    data = receipt.get("data", {})
    expected_seal = receipt.get("ctm_seal")
    if not expected_seal:
        return False
    canonical = json.dumps(data, sort_keys=True)
    computed = hashlib.sha256(canonical.encode()).hexdigest()
    return expected_seal == computed
