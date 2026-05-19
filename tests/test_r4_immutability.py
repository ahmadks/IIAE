import pytest
from iiae.ctm import create_receipt, verify_receipt

def test_r4_immutability_receipt_verification():
    """
    R4 Immutability: Once a receipt is created (sealed), altering any of its data
    should invalidate the cryptographic seal.
    """
    prompt = "What is the policy?"
    response = "The policy is X."
    ds = 0.0
    axioms = ["Policy is X"]
    model_id = "test-model-v1"

    receipt = create_receipt(prompt, response, ds, axioms, model_id)
    
    # Baseline: it should verify
    assert verify_receipt(receipt) is True

    # Tampering: alter response
    receipt["data"]["response"] = "The policy is Y."
    assert verify_receipt(receipt) is False

    # Tampering: alter ds
    receipt["data"]["response"] = "The policy is X." # revert
    receipt["data"]["ds"] = 0.5
    assert verify_receipt(receipt) is False

    # Tampering: alter seal
    receipt["data"]["ds"] = 0.0 # revert
    receipt["ctm_seal"] = "deadbeef" + receipt["ctm_seal"][8:]
    assert verify_receipt(receipt) is False
