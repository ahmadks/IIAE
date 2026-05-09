import math
import re
from typing import List, Dict, Any, Tuple
from .semantic import calculate_similarity

class DQE_Module:
    """
    Deviation Quantification Engine (DQE) - Semantic Mode v3.1
    Measures true semantic distance per axiom using segmented local embeddings.
    """
    def __init__(self, epsilon: float = 0.4):
        self.epsilon = epsilon

    def _get_response_parts(self, response: str) -> List[str]:
        """
        Splits the response into semantic segments for individual axiom verification.
        """
        # Split by "and", period+space, or newlines
        parts = [p.strip() for p in re.split(r' and |\. |\n', response) if p.strip()]
        return parts if parts else [response]

    def compute_ds(self, response: str, axioms: List[str]) -> Tuple[float, List[str]]:
        """
        Calculates Semantic Drift (Ds) using segmented NLP similarity.
        Returns: (Ds, explanations)
        """
        if not axioms:
            return 0.0, []

        parts = self._get_response_parts(response)
        scores = []
        explanations = []

        for ax in axioms:
            # We take the BEST match among all response segments
            # This prevents "noise" from other phrases from lowering the score
            sim = max(calculate_similarity(ax, p) for p in parts)
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
        Uses segmented similarity to identify which axioms to re-inject.
        """
        if ds <= self.epsilon:
            return response
        
        parts = self._get_response_parts(response)
        missing_parts = []
        for ax in axioms:
            # If no segment matches the axiom well enough, it's missing
            if max(calculate_similarity(ax, p) for p in parts) < 0.85:
                missing_parts.append(ax)
        
        if not missing_parts:
            return response
            
        correction = "\n[ADJUSTMENT: Structural Invariants Re-injected]\n"
        for part in missing_parts:
            correction += f"- {part}\n"
            
        return response + correction
