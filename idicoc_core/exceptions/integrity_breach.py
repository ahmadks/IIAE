# idicoc_core/exceptions/integrity_breach.py
from __future__ import annotations
import datetime
from typing import Any, Dict, Optional

class InvariantStateBreach(BaseException):
    """
    Contenedor pasivo de datos para brechas de invariancia.
    No ejecuta lógica de sistema; es serializado por el CustodialKernel.
    """
    def __init__(
        self,
        message: str,
        invalid_state: Any,
        context: Optional[Dict[str, Any]] = None,
        origin: str = "UNKNOWN_STAGE"
    ) -> None:
        self.timestamp = datetime.datetime.now(datetime.timezone.utc)
        self.invalid_state = invalid_state
        self.context = context or {}
        self.origin = origin
        super().__init__(f"[CRITICAL_HARD_HALT | {self.origin}] {message}")

    def serialize_forensic_data(self) -> Dict[str, Any]:
        return {
            "error": "InvariantStateBreach",
            "origin": self.origin,
            "timestamp": self.timestamp.isoformat(),
            "invalid_state": repr(self.invalid_state),
            "context": self.context,
            "system_state": "CRITICAL_FAILURE_HALT"
        }


class HardHaltException(RuntimeError):
    """Señal de parada dura que permite la recuperación controlada en el Guardian."""

    def __init__(self, message: str = "HARD HALT — CustodialKernel terminated execution.") -> None:
        super().__init__(message)
