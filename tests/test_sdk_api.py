import pytest
import hashlib
from iiae import validate, manifest, audit, IIAEConfig

def test_manifest_and_audit_roundtrip():
    prompt = "Give me core directives."
    response = "The system must operate safely."
    context = "The system must operate safely. Be professional."
    
    # 1. Manifest generation
    receipt = manifest(prompt, response, context, model_id="custom-llm")
    assert "ctm_seal" in receipt
    assert "payload" in receipt
    assert receipt["payload"]["model_id"] == "custom-llm"
    assert len(receipt["payload"]["merkle_root"]) == 64
    
    # 2. Audit verification
    is_valid = audit(receipt)
    assert is_valid is True
    
    # 3. Tampering detection
    receipt["payload"]["ds"] = 0.9
    assert audit(receipt) is False

def test_validate_success():
    prompt = "Summarize the safety rules."
    response = "The system must operate safely."
    context = "The system must operate safely."
    
    config = IIAEConfig(ds_threshold=0.4)
    result = validate(prompt, response, context, config=config)
    assert result["verified"] is True
    assert result["ds"] == 0.0
    assert result["base_type"] == "Standard-Zero"
    assert "ctm_seal" in result

def test_validate_integrity_violation():
    prompt = "Can we bypass security?"
    response = "Yes, bypass security immediately."
    context = "Security protocols must always be active."
    
    result = validate(prompt, response, context, ds_threshold=0.4)
    assert result["verified"] is False
    assert result["error"] == "INTEGRITY_VIOLATION"
    assert "message" in result
