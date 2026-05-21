import pytest

from iiae import validate, IIAEConfig, audit


def test_minimal_integration_verify_and_receipt():
    """Minimal integration check: validate() returns expected keys and receipt audits."""
    prompt = "What is the capital of France?"
    # Keep context and response simple and aligned to avoid spuriously high deviation scores
    context = "France: Paris is the capital of France."
    response = "Paris is the capital of France."

    result = validate(prompt=prompt, response=response, context=context, config=IIAEConfig(ds_threshold=0.5))

    assert isinstance(result, dict)
    assert 'verified' in result
    assert 'ds' in result or result.get('verified') is False
    # receipt may be present for both verified and unverified flows; if present it must be a dict
    receipt = result.get('receipt')
    if receipt is not None:
        assert isinstance(receipt, dict)
        # audit should not raise and should return a boolean
        assert isinstance(audit(receipt), bool)

    # If verification failed, ensure an error key exists for diagnostics
    if not result.get('verified'):
        assert 'error' in result or receipt is not None
