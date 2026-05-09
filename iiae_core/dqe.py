from typing import List, Tuple
from .primitives import sha256

class DQE_Module:
    """
    Deviation Quantification Engine (DQE)
    Calculates the Dissonance Coefficient (Ds) and performs Invariant Projection (Snapping).
    """
    def __init__(self, epsilon: float = 0.4):
        self.epsilon = epsilon

    def _tokenize(self, text: str) -> List[str]:
        return [t.strip().lower() for t in text.split() if t.strip()]

    def compute_ds(self, candidate_output: str, axioms: List[str]) -> Tuple[float, List[str]]:
        """
        Calculates Ds relative to the Property Graph (axioms).
        Returns the score and an explanation of breaches.
        """
        if not axioms:
            return 0.0, []

        out_tokens = self._tokenize(candidate_output)
        total_weight = len(axioms)
        deviation = 0.0
        explanations = []

        for ax in axioms:
            ax_tokens = self._tokenize(ax)
            # Check if all tokens of the axiom are present in the output
            if all(tok in out_tokens for tok in ax_tokens):
                penalty = 0.0
                status = "✅ PASS"
            elif any(tok in out_tokens for tok in ax_tokens):
                penalty = 0.5
                status = "⚠️ PARTIAL"
            else:
                penalty = 1.0
                status = "❌ BREACH"
            
            deviation += penalty
            explanations.append(f"{status}: {ax}")

        ds_score = deviation / total_weight
        return ds_score, explanations

    def snap(self, y_candidate: str, ds_score: float, axioms: List[str]) -> str:
        """
        Invariant Projection (Snapping) - Section 5.4.2.
        Maps the deviant vector y back to the nearest admissible state inside the manifold.
        """
        if ds_score <= self.epsilon:
            return y_candidate

        # Simulate snapping logic:
        # In the architectural PDF, this is a mathematical projection.
        # Here we simulate it by 'forcing' the axioms into the response.
        out_tokens = self._tokenize(y_candidate)
        missing_axioms = []
        
        for ax in axioms:
            ax_tokens = self._tokenize(ax)
            if not all(tok in out_tokens for tok in ax_tokens):
                missing_axioms.append(ax)

        if not missing_axioms:
            # If Ds > epsilon but no tokens are missing (logical contradiction)
            return "[DQE_PROJECTION]: Output was modified to resolve internal logical contradictions."

        # Simulate 'Nearest Admissible State'
        correction = " | ".join(missing_axioms)
        return f"[CORRECTED_INVARIANT]: {y_candidate} (Structural reinforcement applied: {correction})"

