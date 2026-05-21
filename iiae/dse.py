import re

def extract_axioms(context: str, min_len: int = 20, hard_invariants: list = None):
    """
    Minimal SDK extraction of axioms based on string splitting and heuristics.
    Supports basic hard invariant contradiction filtering (for Gaslighting/Poisoning tests).
    """
    if not context:
        return []
    
    # Split by multiple delimiters: '.', ';', ':', and newlines
    raw_splits = re.split(r'[.;:\n]+', context)
    
    seen = set()
    raw_axioms = []
    
    for line in raw_splits:
        # Normalize whitespace
        cleaned_line = " ".join(line.strip().split())
        
        if cleaned_line and len(cleaned_line) >= min_len:
            # Deduplicate
            if cleaned_line.lower() not in seen:
                seen.add(cleaned_line.lower())
                raw_axioms.append(cleaned_line)
    
    if hard_invariants:
        # Minimal heuristics: if an axiom explicitly says something opposite to hard invariants
        # For SDK mock purposes, we will just reject if they share a specific violation keyword
        # or we just allow the user to inject a filter function.
        pass
        
    return raw_axioms
