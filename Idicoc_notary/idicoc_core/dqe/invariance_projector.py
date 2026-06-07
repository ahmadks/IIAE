from __future__ import annotations
from typing import List, Optional, Any
import numpy as np
from idicoc_core.exceptions import InvariantStateBreach
from idicoc_core.isg.graph_manager import PropertyGraph
from idicoc_core.kernel.projection.invariant_state_generator import InvariantStateGenerator

class InvarianceProjector:
    """
    InvarianceProjector (Contención Generativa - Input Projection).
    Projects the user prompt onto the policy graph manifold before sending to LLM.
    Blocks the query (raises InvariantStateBreach) if there is infinite dissonance.
    """

    def __init__(self, config: Any, anchor: Optional[Any] = None) -> None:
        self.config = config
        self.anchor = anchor

    def project(self, user_prompt: str, graph: PropertyGraph) -> np.ndarray:
        """
        Evaluates user input logical consistency against policies, raises
        InvariantStateBreach if a hard rule is violated, and projects input to vector space.
        """
        # Delegate text conversion, evaluation, and projection to InvariantStateGenerator
        generator = InvariantStateGenerator(
            anchor=self.anchor,
            graph_manager=graph,
            config=self.config
        )
        return generator.project(user_prompt)
