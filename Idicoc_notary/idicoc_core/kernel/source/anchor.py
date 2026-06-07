# idicoc_core/kernel/source/anchor.py
from __future__ import annotations
import hashlib

class SourceAnchor:
    """Marcador estructural del objeto terminal K de la coalgebra IDICOC.

    K es el límite ideal y de referencia contra el que se mide la desviación estructural.
    No tiene representación vectorial o de coordenadas en sí. Su fingerprint es una firma
    forense constante que acredita su existencia en el sistema.
    """
    _STRUCTURAL_ID = "IDICOC::K::terminal_coalgebra_object::v2"
    _FINGERPRINT: str = hashlib.sha256(_STRUCTURAL_ID.encode()).hexdigest()

    @property
    def fingerprint(self) -> str:
        """Firma forense estructural de K."""
        return self._FINGERPRINT

    @property
    def identity_hash(self) -> str:
        """Alias del fingerprint para registros CTM."""
        return self._FINGERPRINT

    def __repr__(self) -> str:
        return f"SourceAnchor(K=<terminal_coalgebra_object>, fingerprint={self._FINGERPRINT[:12]}...)"
