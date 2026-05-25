from __future__ import annotations
import numpy as np
from typing import Any
from idicoc_notary_core.kernel.exceptions.integrity_breach import InvariantStateBreach

class SourceAnchor:
    """
    Representa la coálgebra terminal (k) como un punto fijo inmutable.
    Garantiza que la 'Frecuencia Original' sea verificable y no corruptible.
    """
    def __init__(self, constant_k: np.ndarray):
        # 1. Validación de naturaleza coalgebraica: Debe ser una distribución de probabilidad
        if not np.isclose(constant_k.sum(), 1.0) or np.any(constant_k < 0):
            raise InvariantStateBreach("La constante k debe ser una medida de probabilidad (suma 1, elementos >= 0).")

        # 2. Inmutabilidad estricta (Deep Freeze)
        self._k = np.array(constant_k, copy=True)
        self._k.flags.writeable = False 
        
        # 3. Fingerprinting: Generamos una huella única para auditoría
        self._fingerprint = hash(self._k.tobytes())

    @property
    def terminal_state(self) -> np.ndarray:
        """Retorna la medida terminal inmutable."""
        return self._k

    @property
    def identity_hash(self) -> int:
        """Permite verificar la integridad del ancla en logs forenses."""
        return self._fingerprint

    def verify_isomorphism(self, state: np.ndarray) -> bool:
        """
        Valida si un estado es isomorfo al punto fijo terminal 
        bajo el funtor de tolerancia definido.
        """
        return np.allclose(self._k, state, atol=1e-6)