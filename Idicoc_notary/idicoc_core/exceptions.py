from __future__ import annotations
import datetime
from typing import Any, Dict, Optional

class WrapperInitializationError(RuntimeError):
    """Error cuando el wrapper no se ha inicializado correctamente."""
    def __init__(self, message: str):
        super().__init__(f"[WrapperInitializationError] {message}")


class ComplianceBreach(RuntimeError):
    """Error cuando el estado no cumple las reglas de IDICOC."""
    def __init__(
        self,
        message: str,
        breach_type: str | None = None,
        dissonance: float | None = None,
        threshold: float | None = None,
    ):
        self.message = message
        self.breach_type = breach_type or "unknown"
        self.dissonance = dissonance
        self.threshold = threshold
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        texto = f"[ComplianceBreach:{self.breach_type}] {self.message}"
        if self.dissonance is not None and self.threshold is not None:
            texto += f" | D_s={self.dissonance:.4f} > ε={self.threshold:.4f}"
        return texto

    def serialize(self) -> dict[str, float | str | None]:
        return {
            "type": self.breach_type,
            "message": self.message,
            "dissonance": self.dissonance,
            "threshold": self.threshold,
        }


class AlignmentBreach(BaseException):
    """
    AlignmentBreach — Violación crítica de bisimulación con la coálgebra terminal (k).
    """
    def __init__(
        self,
        message: str,
        invalid_state: Any,
        context: Optional[Dict[str, Any]] = None,
        origin: str = "InvariantVerifier"
    ) -> None:
        self.timestamp = datetime.datetime.now(datetime.timezone.utc)
        self.invalid_state = invalid_state
        self.context = context or {}
        self.origin = origin
        super().__init__(f"[ALIGNMENT_BREACH | {self.origin}] {message}")

    def serialize_forensic_data(self) -> Dict[str, Any]:
        return {
            "error_type": "AlignmentBreach",
            "origin": self.origin,
            "timestamp": self.timestamp.isoformat(),
            "invalid_state": repr(self.invalid_state), 
            "context": self.context,
            "system_state": "ALIGNMENT_FAILURE"
        }


class InvariantStateBreach(BaseException):
    """
    Contenedor pasivo de datos para brechas de invariancia.
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
    """Señal de parada dura."""
    def __init__(self, message: str = "HARD HALT — CustodialKernel terminated execution.") -> None:
        super().__init__(message)


class PersistenceError(RuntimeError):
    """Error general de la capa de persistencia."""
    def __init__(self, message: str):
        super().__init__(f"[PersistenceError] {message}")


class DataCorruptionError(PersistenceError):
    """Error de datos corruptos en almacenamiento persistente."""
    def __init__(self, filepath: str, message: str):
        super().__init__(f"Archivo corrupto '{filepath}': {message}")
