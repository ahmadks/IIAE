# idicoc_core/core/source/anchor.py

class SourceAnchor:
    """
    Representa la coálgebra terminal (k).
    Es la identidad inmutable del sistema. Cualquier estado que no sea
    isomorfo a esta constante es, por definición, ruido o corrupción.
    """
    def __init__(self, constant_k: Any):
        self._k = constant_k  # La "Frecuencia Original"

    @property
    def identity(self) -> Any:
        return self._k