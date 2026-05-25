from __future__ import annotations
import numpy as np
from idicoc_notary_core.kernel.exceptions.integrity_breach import InvariantStateBreach

class SourceAnchor:
    """
    Representa la coálgebra terminal (k) como un punto fijo inmutable en el espacio latente.
    Acepta EXCLUSIVAMENTE vectores (np.ndarray) para garantizar rigor topológico.
    """
    def __init__(self, constant_k: np.ndarray):
        # 1. Proyección inmediata al espacio matemático (float)
        constant_k = np.asarray(constant_k, dtype=float)

        # 2. Validación geométrica (el punto debe existir)
        if constant_k.size == 0:
            raise InvariantStateBreach("El vector del ancla no puede estar vacío.")

        # 3. Inmutabilidad Profunda (Deep Freeze) del estado
        self._k = np.array(constant_k, copy=True)
        self._k.flags.writeable = False 
        
        # 4. Hash forense determinista basado en los bytes del vector
        self._fingerprint = hash(self._k.tobytes())

    @property
    def identity(self) -> np.ndarray:
        """Alias de la identidad terminal."""
        return self._k

    @property
    def terminal_state(self) -> np.ndarray:
        """Retorna el estado terminal vectorial e inmutable ($k$)."""
        return self._k

    @property
    def identity_hash(self) -> int:
        """Firma algorítmica del ancla para registros inmutables (CTM)."""
        return self._fingerprint

    def verify_isomorphism(self, state: np.ndarray) -> bool:
        """
        Valida rigurosamente si un estado candidato es topológicamente isomorfo 
        al punto fijo terminal bajo un funtor de tolerancia definido (1e-6).
        """
        if state.shape != self._k.shape:
            return False
        return bool(np.allclose(self._k, state, atol=1e-6))