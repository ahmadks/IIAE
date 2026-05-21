import pytest
import time
from iiae.ctm import create_receipt, verify_receipt

def test_r5_replay_resistance():
    """
    R5 Replay Resistance: Identical inputs evaluated at different times
    must yield unique cryptographic seals due to unique timestamps.
    """
    prompt = "Standard request."
    response = "Standard response."
    ds = 0.0
    axioms = ["Standard axiom"]
    model_id = "test-model-v1"

    receipt1 = create_receipt(prompt, response, ds, axioms, model_id)
    
    # Ensure some time passes (even if minimal)
    time.sleep(0.01)
    
    receipt2 = create_receipt(prompt, response, ds, axioms, model_id)

    # Both verify successfully on their own
    assert verify_receipt(receipt1) is True
    assert verify_receipt(receipt2) is True

    # Seals must be different
    assert receipt1["ctm_seal"] != receipt2["ctm_seal"]
    assert receipt1["payload"]["timestamp"] != receipt2["payload"]["timestamp"]
