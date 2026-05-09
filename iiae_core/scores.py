def compute_preservation_score(similarities):
    if not similarities:
        return 0.0
    return sum(similarities) / len(similarities)

def compute_noise_score(clause_support_scores):
    if not clause_support_scores:
        return 0.0
    # Weakly supported content (0.45 <= score < 0.75) is considered noise
    weak = [s for s in clause_support_scores if 0.45 <= s < 0.75]
    return len(weak) / len(clause_support_scores)

def compute_hallucination_score(clause_support_scores):
    if not clause_support_scores:
        return 0.0
    # Unsupported content (score < 0.45) is considered hallucination
    unsupported = [s for s in clause_support_scores if s < 0.45]
    return len(unsupported) / len(clause_support_scores)

def compute_contradiction_score(entailment_results):
    if not entailment_results:
        return 0.0
    # We take the average probability of contradiction across all checks
    contradictions = [e["contradiction"] for e in entailment_results]
    return sum(contradictions) / len(contradictions)
