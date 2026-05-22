from abc import ABC, abstractmethod
from typing import Tuple
from .core.isg import CanonicalState

class IDQEEngine(ABC):
    """Contract for DQE engine implementations.

    Implementations must provide a ``compute_ds`` method returning a tuple
    ``(ds: float, base_type: str, corrected_response: str)`` where ``ds`` is
    the deviation score in the range ``[0.0, 1.0]`` and ``corrected_response``
    is the projected candidate state on the manifold boundary.
    """

    @abstractmethod
    def compute_ds(self, candidate_state: str, canonical_state: CanonicalState, epsilon: float) -> Tuple[float, str, str]:
        """Calculate the invariant distance from candidate_state to the canonical state."""
        raise NotImplementedError
