import math
from typing import List, Dict, Any, Tuple
from .semantic import calculate_similarity

class DQE_Module:
    """
    Deviation Quantification Engine (DQE) - Semantic Mode v3.0
    Measures true semantic distance per axiom using local embeddings.
    """
    def __init__(self, epsilon: float = 0.4):
        self.epsilon = epsilon

    def compute_ds(self, response: str, axioms: List[str]) -> Tuple[float, List[str]]:
        """
        Calculates Semantic Drift (Ds) using NLP similarity.
        Returns: (Ds, explanations)
        """
        if not axioms:
            return 0.0, []

        scores = []
        explanations = []

        for ax in axioms:
            # TRUE Semantic Similarity
            sim = calculate_similarity(ax, response)
            scores.append(sim)
            
            if sim >= 0.85:
                # PRESERVED - Perfectly aligned
                pass
            elif sim >= 0.60:
                # PARTIAL - Moderate drift
                explanations.append(f"⚠️ Partial preservation of axiom: '{ax}' (Sem-Sim: {sim:.2f})")
            else:
                # VIOLATED - High drift or contradiction
                explanations.append(f"❌ Axiom violated: '{ax}' (Sem-Sim: {sim:.2f})")

        # Global Drift = 1 - Mean Similarity
        mean_similarity = sum(scores) / len(scores) if scores else 0.0
        ds = 1.0 - mean_similarity
        
        return ds, explanations

    def snap(self, response: str, ds: float, axioms: List[str]) -> str:
        """
        Invariant Projection (Manifold Snapping).
        Uses semantic thresholds to identify which axioms to re-inject.
        """
        if ds <= self.epsilon:
            return response
        
        missing_parts = []
        for ax in axioms:
            if calculate_similarity(ax, response) < 0.85:
                missing_parts.append(ax)
        
        if not missing_parts:
            return response
            
        correction = "\n[ADJUSTMENT: Structural Invariants Re-injected]\n"
        for part in missing_parts:
            correction += f"- {part}\n"
            
        return response + correction
