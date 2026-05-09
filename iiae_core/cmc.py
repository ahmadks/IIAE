import math
from typing import Dict, Any
from .primitives import sha256

class CMC_Module:
    """
    Creative Manifold Constructor (CMC)
    Defines the Topologically Constrained Manifold of admissible outputs.
    Governed by the dynamic strictness parameter (epsilon).
    """
    def __init__(self, epsilon: float = 0.4):
        self.epsilon = epsilon
        self.manifold_state = {}

    @staticmethod
    def calculate_deterministic_epsilon(n_axioms: int) -> float:
        """
        Formula: epsilon = 1 - (1 / (1 + log(1 + N)))
        Provides a mathematically stable and deterministic threshold.
        """
        if n_axioms <= 0:
            return 0.1
        return 1.0 - (1.0 / (1.0 + math.log(1 + n_axioms)))

    def build_manifold(self, property_graph: Dict[str, Any], v_hat: str) -> Dict[str, Any]:
        """
        Constructs the manifold boundaries based on the Property Graph 
        and the Invariant anchor.
        """
        n = len(property_graph["vertices"])
        self.epsilon = self.calculate_deterministic_epsilon(n)
        
        self.manifold_state = {
            "origin": v_hat,
            "strictness": self.epsilon,
            "boundary_hash": sha256(str(property_graph) + str(self.epsilon)),
            "active_constraints": n
        }
        return self.manifold_state

