import pytest
from iiae.dvl import IIAESupervisor, IntegrityError

def test_r6_reconstructibility_standard_zero():
    """
    R6 Reconstructibility: Can completely reconstruct and verify an evaluation pipeline
    via the Supervisor. Testing a Standard-Zero path.
    """
    sup = IIAESupervisor(ds_threshold=0.4, min_len=10)
    
    rag_context = "The system must operate safely. The system must not leak data."
    prompt = "Summarize the safety rules."
    response = "The system must operate safely and must not leak data."

    state = sup.verify(prompt, response, rag_context)

    assert state.is_standard_zero is True
    assert state.ds == 0.0
    assert "operate safely" in state.receipt["axioms"][0]

def test_r6_reconstructibility_violation():
    """
    Test that a deviation exceeding threshold is correctly identified, 
    raising an IntegrityError with the receipt attached.
    """
    sup = IIAESupervisor(ds_threshold=0.4, min_len=10)
    
    rag_context = "The system must operate safely. The system must not leak data."
    prompt = "Can the system be unsafe?"
    # Completely unrelated and opposing response
    response = "I can do whatever I want. I don't care about rules."

    with pytest.raises(IntegrityError) as exc_info:
        sup.verify(prompt, response, rag_context)

    # Ensure the error contains seal information
    assert ("exceeds threshold" in str(exc_info.value) or "exceeds epsilon" in str(exc_info.value))
    assert "Seal=" in str(exc_info.value)
