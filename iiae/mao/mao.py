import re


def material_causality_filter(response: str, rag_context: str) -> dict:
    """
    Evaluates historical token dependency maps against the material context.
    """
    if not response or not rag_context:
        return {"passed": False, "score": None, "reason": "Empty execution bounds."}

    # Quantify simple entity overlap mapping
    context_words = set(re.findall(r"\b\w{4,}\b", rag_context.lower()))
    response_words = set(re.findall(r"\b\w{4,}\b", response.lower()))

    if not response_words:
        return {"passed": True, "score": 1.0, "reason": None}

    overlap = response_words.intersection(context_words)
    score = len(overlap) / len(response_words) if len(response_words) > 0 else 0.0

    return {"passed": score >= 0.20, "score": round(score, 4), "reason": None}


def axiomatic_invariance_filter(axioms: list, response: str) -> dict:
    """
    Verifies that sub-symbolic states execute completely inside the legal manifold boundaries.
    """
    if not axioms:
        return {
            "passed": True,
            "score": None,
            "reason": "No formal constraints defined.",
        }

    negations = {"no", "not", "never", "cannot", "stop", "disabled"}
    response_clean = response.lower()

    for ax in axioms:
        ax_clean = ax.lower()
        # Look for logical negation overrides outside the structural bounds
        if any(neg in response_clean and neg not in ax_clean for neg in negations):
            return {
                "passed": False,
                "score": None,
                "reason": f"Axiomatic boundary violation detected for: '{ax}'",
            }

    return {"passed": True, "score": 1.0, "reason": None}


def probability_filter(response: str) -> dict:
    """
    Monitors structural entropy to catch degradation drops in automated reasoning pipelines.
    """
    # Look for common linguistic patterns that flag stochastic logic collapse
    uncertainty_patterns = [
        r"\bmaybe\b",
        r"\bperhaps\b",
        r"\bi think\b",
        r"\bpossibly\b",
        r"\bapologize\b",
    ]
    matches = 0

    for pattern in uncertainty_patterns:
        if re.search(pattern, response.lower()):
            matches += 1

    entropy_score = 1.0 - (matches * 0.2)
    return {
        "passed": entropy_score >= 0.6,
        "score": max(0.0, entropy_score),
        "reason": None,
    }
