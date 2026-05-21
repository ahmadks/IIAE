"""
Axiom Entropy Module (AEM)

Separates structural signal from statistical entropy/noise.
"""

from typing import Dict, List, Tuple


def decompose_response(
    response: str, axioms: List[str]
) -> Tuple[str, Dict[str, float]]:
    """
    Decomposes response into:
    - Structural signal (axiom-aligned components)
    - Entropy components (stochastic noise, uncertainty markers)

    Args:
        response: The AI response text
        axioms: List of structural axioms

    Returns:
        (structural_signal, entropy_map)
    """

    uncertainty_tokens = {
        "maybe": 0.3,
        "possibly": 0.3,
        "i think": 0.2,
        "not sure": 0.4,
        "uncertain": 0.4,
        "unclear": 0.3,
        "appears": 0.2,
        "seems": 0.2,
        "approximately": 0.1,
        "roughly": 0.1,
        "about": 0.1,
    }

    entropy_map = {
        "uncertainty_score": 0.0,
        "entropy_tokens": [],
        "noise_level": 0.0,
    }

    # Detect uncertainty markers
    response_lower = response.lower()
    total_entropy = 0.0

    for token, weight in uncertainty_tokens.items():
        if token in response_lower:
            entropy_map["entropy_tokens"].append(token)
            total_entropy += weight

    entropy_map["uncertainty_score"] = min(1.0, total_entropy)

    # Estimate noise level (typically low for professional responses)
    # In production: use more sophisticated noise estimation
    entropy_map["noise_level"] = min(0.5, total_entropy * 0.5)

    # Structural signal = response with reduced uncertainty markers
    structural = response
    for token in entropy_map["entropy_tokens"]:
        structural = structural.replace(token, "").replace(token.upper(), "")

    return structural.strip(), entropy_map


def measure_entropy_purge_rate(
    original_entropy: float, purged_entropy: float
) -> float:
    """
    Entropy Purge Rate (EPR): measures system's ability to reject stochastic noise.

    EPR = 1 - (H_structural / H_total)

    Args:
        original_entropy: Original entropy before purging
        purged_entropy: Entropy after structural segregation

    Returns:
        EPR score (0.0 = no purging, 1.0 = complete purging)
    """

    if original_entropy == 0.0:
        return 0.0

    return 1.0 - (purged_entropy / original_entropy)
