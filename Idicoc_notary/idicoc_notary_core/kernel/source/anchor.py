from __future__ import annotations
import hashlib


class SourceAnchor:
    """Marcador estructural del objeto terminal K de la coalgebra IDICOC.

    K existe y es único — está definido exclusivamente por la propiedad:

        D_s(s, s') = 0  ⟺  s, s' ∈ K

    K no tiene valor, representación numérica ni coordenadas en ningún espacio.
    Es "inimaginable, impensable, indescriptible" — el ancla absoluta contra la
    que se mide la desviación estructural, pero que nunca se materializa como vector.

    NO se mide *contra* K. Se mide si los estados son bisimilares entre sí
    y si satisfacen las restricciones del sistema (d₂, d₃). K es el límite
    ideal que esas restricciones aproximan asintóticamente.

    SourceAnchor es el marcador que acredita la existencia y unicidad de K
    en el sistema. Su fingerprint es un identificador estructural constante
    que permite trazabilidad forense sin materializar K.

    Attributes:
        fingerprint (str): Identificador estructural inmutable de K (no es K en sí).
        identity_hash (str): Alias del fingerprint para registros CTM.
    """

    # Identificador estructural constante derivado del nombre formal del objeto terminal.
    # No es K — es una firma que acredita que K existe en este sistema.
    _STRUCTURAL_ID = "IDICOC::K::terminal_coalgebra_object::v1"
    _FINGERPRINT: str = hashlib.sha256(_STRUCTURAL_ID.encode()).hexdigest()

    def __init__(self, *args, **kwargs) -> None:
        # No acepta ni almacena ningún vector o valor.
        # K no tiene representación — los argumentos se ignoran explícitamente.
        pass

    @property
    def fingerprint(self) -> str:
        """Firma forense estructural de K. No es K — acredita su existencia."""
        return self._FINGERPRINT

    @property
    def identity_hash(self) -> str:
        """Alias del fingerprint para registros CTM inmutables."""
        return self._FINGERPRINT

    def __repr__(self) -> str:
        return f"SourceAnchor(K=<terminal_coalgebra_object>, fingerprint={self._FINGERPRINT[:12]}...)"
