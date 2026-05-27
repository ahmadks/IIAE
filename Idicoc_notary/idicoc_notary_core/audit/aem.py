from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

class AuditEntropyModule:
    """
    Audit Entropy Module (AEM) acting as a pure signal counter and audit trail map.
    Tracks total, valid, and rejected signals, and logs rejection metadata.
    """
    def __init__(self) -> None:
        self.total_signals: int = 0
        self.valid_signals: int = 0
        self.rejected_signals: int = 0
        self.audit_trail_map: List[Dict[str, Any]] = []

    def record_admission(self, metadata: Dict[str, Any] | None = None) -> None:
        """Increments total_signals (y_t) and valid_signals (y_valid)."""
        self.total_signals += 1
        self.valid_signals += 1

    def record_admission_from_correction(self, metadata: Dict[str, Any] | None = None) -> None:
        """Alias or helper to record admission if snapping/correction was performed."""
        self.total_signals += 1
        self.valid_signals += 1

    def record_rejection(self, metadata: Dict[str, Any]) -> None:
        """Increments total_signals (y_t) and rejected_signals (n_t), and adds metadata to the trail."""
        self.total_signals += 1
        self.rejected_signals += 1
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **(metadata or {})
        }
        self.audit_trail_map.append(record)

    def get_counters(self) -> Tuple[int, int, int]:
        """Returns (total_signals, valid_signals, rejected_signals)."""
        return self.total_signals, self.valid_signals, self.rejected_signals

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Returns the audit trail map."""
        return self.audit_trail_map
