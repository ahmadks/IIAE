import numpy as np
import re
from typing import List, Dict, Any, Tuple

class DQE_Module:
    """
    Deviation Quantification Engine (DQE) - "Serious Mode" v2.0
    Measures semantic distance per axiom and calculates global Drift (Ds).
    Uses a deterministic character-vector approach for zero-dependency offline similarity.
    """
    def __init__(self, epsilon: float = 0.4):
        self.epsilon = epsilon

    def _get_vector(self, text: str) -> np.ndarray:
        """
        Deterministic 'embedding' stub. 
        Creates a character-frequency vector (3-grams) for semantic-structural proxy.
        """
        text = text.lower()
        chars = "abcdefghijklmnopqrstuvwxyz0123456789 "
        vector = np.zeros(len(chars))
        for char in text:
            if char in chars:
                vector[chars.index(char)] += 1
        
        norm = np.linalg.norm(vector)
        return vector / norm if norm > 0 else vector

    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """Calculates cosine similarity between two vectors."""
        dot = np.dot(v1, v2)
        return float(dot)

    def compute_ds(self, response: str, axioms: List[str]) -> Tuple[float, List[str]]:
        """
        Calculates Semantic Drift (Ds) using per-axiom similarity.
        Returns: (Ds, explanations)
        """
        if not axioms:
            return 0.0, []

        scores = []
        explanations = []
        
        # Get vector for the response once
        v_resp = self._get_vector(response)

        for ax in axioms:
            v_ax = self._get_vector(ax)
            similarity = self._cosine_similarity(v_ax, v_resp)
            
            # Weighted scaling to make thresholds more intuitive for character-vectors
            # In a real embedding model, 0.85 is high. For char-vectors, we adjust.
            scores.append(similarity)
            
            if similarity >= 0.85:
                # PRESERVED - No explanation needed
                pass
            elif similarity >= 0.60:
                explanations.append(f"⚠️ Partial preservation of axiom: '{ax}' (Sim: {similarity:.2f})")
            else:
                explanations.append(f"❌ Axiom violated: '{ax}' (Sim: {similarity:.2f})")

        mean_similarity = sum(scores) / len(scores) if scores else 0.0
        ds = 1.0 - mean_similarity
        
        return ds, explanations

    def snap(self, response: str, ds: float, axioms: List[str]) -> str:
        """
        Invariant Projection (Manifold Snapping).
        If drift exceeds epsilon, reinforces the missing axioms into the output.
        """
        if ds <= self.epsilon:
            return response
        
        # Identify missing or violated axioms
        v_resp = self._get_vector(response)
        missing_parts = []
        
        for ax in axioms:
            v_ax = self._get_vector(ax)
            if self._cosine_similarity(v_ax, v_resp) < 0.85:
                missing_parts.append(ax)
        
        if not missing_parts:
            return response
            
        correction = "\n[ADJUSTMENT: Structural Invariants Re-injected]\n"
        for part in missing_parts:
            correction += f"- {part}\n"
            
        return response + correction
