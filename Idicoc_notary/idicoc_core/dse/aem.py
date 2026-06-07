"""
Audit Entropy Module (AEM) - Tracks audit history, rejections, and signal counters.
"""

from typing import List, Dict, Any, Tuple

from idicoc_core.utils.logger import get_logger

logger = get_logger("dse.aem")


class AuditEntropyModule:
    """
    Audit Entropy Module (AEM) to track the audit history and rejections.
    Maintains counters for total, valid, and rejected signals.
    """

    def __init__(self) -> None:
        self.trail: List[Dict[str, Any]] = []

        # AEM Accounting Counters (valores iniciales por defecto de 1.0 según especificación)
        self._y_total: float = 1.0  # Total signals processed by DQE
        self._y_valid: float = 1.0  # Signals validated/corrected by DQE

    def record(self, case: Dict[str, Any]) -> None:
        """Record an audit case in the trail."""
        self.trail.append(case)
        total, valid, rejected = self.get_counters()
        self._y_total = float(total)
        self._y_valid = float(valid)

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Get the full audit trail."""
        return self.trail

    def get_counters(self) -> Tuple[int, int, int]:
        """
        Get counters: (total_signals, valid_signals, rejected_signals).
        """
        total = len(self.trail)
        rejected = sum(1 for c in self.trail if c.get("admission_breach"))
        valid = total - rejected
        return total, valid, rejected

    @property
    def y_total(self) -> float:
        """Total signals processed by DQE (as float)"""
        return self._y_total

    @y_total.setter
    def y_total(self, value: float) -> None:
        self._y_total = float(value)

    @property
    def y_valid(self) -> float:
        """Signals validated/corrected by DQE (as float)"""
        return self._y_valid

    @y_valid.setter
    def y_valid(self, value: float) -> None:
        self._y_valid = float(value)
