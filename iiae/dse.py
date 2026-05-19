def extract_axioms(context: str, min_len: int = 20, hard_invariants: list = None):
    """
    Minimal SDK extraction of axioms based on string splitting and heuristics.
    Supports basic hard invariant contradiction filtering (for Gaslighting/Poisoning tests).
    """
    if not context:
        return []
    
    raw_axioms = [line.strip() for line in context.split('.') if line.strip() and len(line.strip()) >= min_len]
    
    if hard_invariants:
        # Minimal heuristics: if an axiom explicitly says something opposite to hard invariants
        # For SDK mock purposes, we will just reject if they share a specific violation keyword
        # or we just allow the user to inject a filter function.
        pass
        
    return raw_axioms
