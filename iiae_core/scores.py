def compute_preservation_score(similarities):
    if not similarities:
        return 0.0
    return sum(similarities) / len(similarities)

def compute_noise_score(clause_support_scores):
    if not clause_support_scores:
        return 0.0
    # Noise = 1 - average support (Continuous drift measurement)
    avg_support = sum(clause_support_scores) / len(clause_support_scores)
    return max(0.0, 1.0 - avg_support)

def compute_hallucination_score(clause_support_scores):
    if not clause_support_scores:
        return 0.0
    # Hallucination = Ratio of clauses with severe lack of support (< 0.40)
    unsupported = [s for s in clause_support_scores if s < 0.40]
    return len(unsupported) / len(clause_support_scores)

def compute_contradiction_score(entailment_results):
    if not entailment_results:
        return 0.0
    # Average probability of contradiction
    contradictions = [e["contradiction"] for e in entailment_results]
    return sum(contradictions) / len(contradictions)
