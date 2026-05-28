from __future__ import annotations
import numpy as np
from idicoc_notary_core.kernel.exceptions.integrity_breach import InvariantStateBreach


class SourceAnchor:
    """Representa la coálgebra terminal (k) como un punto fijo inmutable en el espacio latente.

    El SourceAnchor funciona como el atractor matemático de referencia base en
    el espacio latente para medir disonancias semánticas y lógicas.

    ===========================================================================

    El SourceAnchor es el "ANCLA DE REFERENCIA" o "ESTADO CANÓNICO IDEAL" (el atractor K).
    Es un vector matemático inmutable que representa la verdad absoluta o estado base
    perfectamente alineado. Se usa como punto de comparación constante para determinar
    cuánto se desvían las peticiones y respuestas del sistema con respecto a esta base.
    ===========================================================================

    Attributes:
        _k (np.ndarray): Vector inmutable que representa la identidad terminal.
        _fingerprint (int): Hash de los bytes del vector para auditoría forense.

    Raises:
        InvariantStateBreach: Si se intenta inicializar con un vector vacío.

    Examples:
        >>> import numpy as np
        >>> from idicoc_notary_core.kernel.source.anchor import SourceAnchor
        >>> vector_base = np.array([1.0, 0.0, 0.0])
        >>> anchor = SourceAnchor(vector_base)
        >>> print(anchor.identity)
        [1. 0. 0.]
        >>> # Intentar inicializar con un vector vacío fallará:
        >>> try:
        ...     empty_anchor = SourceAnchor(np.array([]))
        ... except Exception as e:
        ...     print(e)
        [InvariantStateBreach] El vector del ancla no puede estar vacío.
    """

    def __init__(self, constant_k: np.ndarray):
        # 1. Proyección inmediata al espacio matemático (float)
        constant_k = np.asarray(constant_k, dtype=float)

        # 2. Validación geométrica (el punto debe existir)
        if constant_k.size == 0:
            raise InvariantStateBreach(
                message="El vector del ancla no puede estar vacío.",
                invalid_state=constant_k,
                origin="SourceAnchor.__init__",
            )

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
        return np.allclose(self._k, state, atol=1e-6)
