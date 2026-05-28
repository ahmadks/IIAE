from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple


class AuditEntropyModule:
    """Modulo de Entropía de Auditoría (AEM) para el conteo de señales y registro de auditorías.

    El AEM actúa como contador puro de señales de admisión/rechazo y mantiene una
    traza inmutable de los motivos forenses de rechazo.

    ===========================================================================
    EXPLICACIÓN EN LENGUAJE LLANO :
    Este módulo es simplemente un CONTADOR DE ADMISIONES Y RECHAZOS.
    Se encarga de llevar la cuenta de cuántas peticiones han sido aceptadas (admitidas),
    cuántas han sido rechazadas por violar disonancia o reglas duras, y guarda un
    historial (audit trail) de los motivos de rechazo.
    Piénsalo como el contador de la puerta del club: cuenta cuánta gente entra bien y
    a cuánta se le deniega la entrada con sus respectivos motivos.
    ===========================================================================

    Attributes:
        total_signals (int): Cantidad total de peticiones procesadas por el pipeline.
        valid_signals (int): Cantidad de peticiones que fueron admitidas (D_s <= epsilon).
        rejected_signals (int): Cantidad de peticiones que fueron rechazadas (D_s > epsilon).
        audit_trail_map (list of dict): Registro histórico detallado de los rechazos.

    Examples:
        >>> from idicoc_notary_core.audit.aem import AuditEntropyModule
        >>> aem = AuditEntropyModule()
        >>> aem.record_admission({"d_s": 0.05})
        >>> aem.record_rejection({"d_s": 0.85, "reason": "dissonance breach"})
        >>> print(aem.get_counters())
        (2, 1, 1)
        >>> print(len(aem.get_audit_trail()))
        1
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
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), **(metadata or {})}
        self.audit_trail_map.append(record)

    def get_counters(self) -> Tuple[int, int, int]:
        """Returns (total_signals, valid_signals, rejected_signals)."""
        return self.total_signals, self.valid_signals, self.rejected_signals

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Returns the audit trail map."""
        return self.audit_trail_map
