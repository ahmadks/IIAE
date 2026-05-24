# idicoc_core/exceptions/alignment_breach.py
from __future__ import annotations
import datetime
from typing import Any, Dict, Optional

class AlignmentBreach(BaseException):
    """
    AlignmentBreach — Violación crítica de bisimulación con la coálgebra terminal (k).
    
    Esta excepción es la señal de que el sistema ha perdido su anclaje ontológico.
    Es un objeto pasivo: no realiza operaciones de I/O ni control de flujo.
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

        # Construcción del mensaje sin procesar, solo encapsulación
        super().__init__(f"[ALIGNMENT_BREACH | {self.origin}] {message}")

    def serialize_forensic_data(self) -> Dict[str, Any]:
        """
        Snapshot forense estandarizado para el CTM.
        """
        return {
            "error_type": "AlignmentBreach",
            "origin": self.origin,
            "timestamp": self.timestamp.isoformat(),
            # El Kernel debe asegurarse de que invalid_state sea serializable
            "invalid_state": repr(self.invalid_state), 
            "context": self.context,
            "system_state": "ALIGNMENT_FAILURE"
        }