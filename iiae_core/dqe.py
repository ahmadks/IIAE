import math
import re
from typing import List, Dict, Any, Tuple
from .semantic import calculate_similarity

class DQE_Module:
    """
    Deviation Quantification Engine (DQE) - Semantic Mode v3.2
    Ensures 1-to-1 semantic alignment between axioms and response segments.
    """
    def __init__(self, epsilon: float = 0.4):
        self.epsilon = epsilon

    def _get_response_parts(self, response: str, n_axioms: int) -> List[str]:
        """
        Splits the response into exactly n_axioms parts, or falls back to full response.
        """
        # Split by "and", period, or newlines
        parts = [p.strip() for p in re.split(r' and |\.|\n', response) if p.strip()]
        
        # If we have too few parts, we use the full response for the remaining slots
        while len(parts) < n_axioms:
            parts.append(response)
            
        return parts[:n_axioms]

    def compute_ds(self, response: str, axioms: List[str]) -> Tuple[float, List[str]]:
        """
        Calculates Semantic Drift (Ds) using 1-to-1 segment alignment.
        Returns: (Ds, explanations)
        """
        if not axioms:
            return 0.0, []

        parts = self._get_response_parts(response, len(axioms))
        scores = []
        explanations = []

        # We compare Axiom[i] against Segment[i]
        # This prevents the "dilution" of embeddings in combined sentences.
        for ax, p in zip(axioms, parts):
            sim = calculate_similarity(ax, p)
            scores.append(sim)
            
            if sim >= 0.85:
                # PRESERVED
                pass
            elif sim >= 0.60:
                # PARTIAL
                explanations.append(f"⚠️ Partial preservation of axiom: '{ax}' (Sem-Sim: {sim:.2f})")
            else:
                # VIOLATED
                explanations.append(f"❌ Axiom violated: '{ax}' (Sem-Sim: {sim:.2f})")

        # Global Drift = 1 - Mean Similarity
        mean_similarity = sum(scores) / len(scores) if scores else 0.0
        ds = 1.0 - mean_similarity
        
        return ds, explanations

    def snap(self, response: str, ds: float, axioms: List[str]) -> str:
        """
        Invariant Projection using segmented alignment.
        """
        if ds <= self.epsilon:
            return response
        
        parts = self._get_response_parts(response, len(axioms))
        missing_parts = []
        for ax, p in zip(axioms, parts):
            if calculate_similarity(ax, p) < 0.85:
                missing_parts.append(ax)
        
        if not missing_parts:
            return response
            
        correction = "\n[ADJUSTMENT: Structural Invariants Re-injected]\n"
        for part in missing_parts:
            correction += f"- {part}\n"
            
        return response + correction
