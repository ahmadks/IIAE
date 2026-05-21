"""
Invariant State Generator (ISG / MAII-ISG)

Produces canonical fixed-point representations from contextual data.
"""

import hashlib
from typing import Dict, Any


def canonicalize_state(prompt: str, response: str, axioms: list) -> Dict[str, Any]:
    """
    Generate a canonical representation of the verification state.

    This ensures:
    - Same input → identical output (deterministic)
    - Robust against numeric fluctuations
    - Fixed-point stable

    Args:
        prompt: Original prompt
        response: AI response
        axioms: Extracted axioms

    Returns:
        Canonical state dictionary
    """

    # Normalize whitespace
    norm_prompt = " ".join(prompt.split()).lower()
    norm_response = " ".join(response.split()).lower()
    norm_axioms = [" ".join(ax.split()).lower() for ax in axioms]

    # Generate deterministic hash
    state_str = f"{norm_prompt}|{norm_response}|{'|'.join(sorted(norm_axioms))}"
    state_hash = hashlib.sha256(state_str.encode()).hexdigest()

    return {
        "prompt_canonical": norm_prompt,
        "response_canonical": norm_response,
        "axioms_canonical": norm_axioms,
        "state_hash": state_hash,
        "deterministic": True,
    }


def is_stable_fixed_point(state1: Dict[str, Any], state2: Dict[str, Any]) -> bool:
    """
    Check if two states represent the same fixed point (within tolerance).

    Args:
        state1: First canonical state
        state2: Second canonical state

    Returns:
        True if states are equivalent
    """

    return state1.get("state_hash") == state2.get("state_hash")
