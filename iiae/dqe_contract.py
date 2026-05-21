from abc import ABC, abstractmethod
from typing import Tuple, List

class IDQEEngine(ABC):
    """Contract for DQE engine implementations.

    Implementations must provide a ``compute_ds`` method returning a tuple
    ``(ds: float, base_type: str)`` where ``ds`` is the deviation score in the
    range ``[0.0, 1.0]`` and ``base_type`` identifies the engine (e.g. ``"lexical"``
    or ``"semantic"``).
    """

    @abstractmethod
    def compute_ds(self, response: str, axioms: List[str]) -> Tuple[float, str]:
        """Calculate the deviation score for *response* given *axioms*.
        """
        raise NotImplementedError
