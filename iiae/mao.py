import hashlib

def material_causality_filter(response: str, context: str) -> bool:
    """
    Material Causality Filter (MAO Annex V.1)
    Rejects if the event is strictly explainable by the technology available at time T.
    In the context of the SDK, this acts as a context plausibility check:
    Is the response constrained within the causal boundaries of the provided context?
    """
    # Heuristic mock: if response introduces completely foreign high-tech concepts not in context
    if "quantum" in response.lower() and "quantum" not in context.lower():
        return False
    return True

def axiomatic_invariance_filter(axioms: list, response: str) -> bool:
    """
    Axiomatic Invariance Filter (MAO Annex V.3)
    Rejection of interpretations involving data loss. 
    The data must be literal and operational.
    """
    if not axioms:
        return True
    
    # Ensure no fundamental axiom is 'lost' or omitted in a summarizing response
    resp_lower = response.lower()
    for ax in axioms:
        # If an axiom is completely missing from the response conceptually, fail invariance
        # A simple SDK heuristic: checking for keyword presence to avoid 'data loss'.
        words = ax.lower().split()
        if len(words) > 0:
            match_ratio = sum(1 for w in words if w in resp_lower) / len(words)
            if match_ratio < 0.2: # High threshold for data loss
                return False
    return True

def probability_filter(response: str) -> float:
    """
    Concurrent Probability Filter (Borel's Limit) (MAO Annex V.2)
    If the combined probability P is near zero, random chance is discarded, 
    confirming a Precision Synchrony.
    Returns a mock probability scalar for the event's randomness.
    """
    # Deterministic mock calculation based on the hash of the response
    # to simulate an anomaly probability score.
    h = hashlib.sha256(response.encode()).hexdigest()
    # Use first 4 hex chars to generate a float between 0 and 1
    val = int(h[:4], 16) / 65535.0
    # Bias it towards extremely low probabilities to simulate Precision Synchrony
    return val * 0.001
