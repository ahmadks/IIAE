"""
Excepciones del wrapper IDICOC.

Solo incluye errores de inicialización y de cumplimiento.
"""

from __future__ import annotations


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
