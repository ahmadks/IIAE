"""
Contratos básicos del wrapper IDICOC.

Define los tipos de datos y las interfaces necesarias para adaptar la
entrada de una IA comercial al núcleo determinista de idicoc_core.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import json
import re

from idicoc_notary_core.utils.hashing import sha256_hex


@dataclass(frozen=True)
class CanonicalStateDTO:
    """
    Estado canónico inmutable generado por el wrapper.

    data: Resultado adaptado para el núcleo.
    metadata: Metadatos de auditoría y de disonancia.
    source_axioms: Axiomas que generaron este estado.
    integrity_hash: Hash determinista para verificación.
    timestamp: Marca de tiempo ISO 8601.
    """

    data: Any
    metadata: dict[str, Any] = field(default_factory=dict)
    source_axioms: list[str] = field(default_factory=list)
    integrity_hash: str = field(default="")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def __post_init__(self) -> None:
        if not self.integrity_hash:
            object.__setattr__(self, "integrity_hash", self.compute_hash())

    def compute_hash(self) -> str:
        canonical_repr = {
            "data": str(self.data),
            "metadata": self.metadata,
            "source_axioms": sorted(self.source_axioms),
            "timestamp": self.timestamp,
        }
        return sha256_hex(json.dumps(canonical_repr, sort_keys=True, default=str))

    def verify_integrity(self) -> bool:
        return self.integrity_hash == self.compute_hash()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanonicalStateDTO:
        return cls(**data)


class IIAENotaryContract(ABC):
    """Contrato abstracto del Auditor IIAE.

    NOTARIO: Este Auditor nunca rechaza ni bloquea entradas o salidas.
    Solo mide, clasifica, notifica (vía logs y CTM) y retorna métricas.
    Las decisiones de acción son competencia del operador, no del auditor.
    """

    @abstractmethod
    def initialize(self, config: Any) -> None:
        ...

    @abstractmethod
    def process(self, admitted_input: Any) -> CanonicalStateDTO:
        ...

    @abstractmethod
    def verify_compliance(
        self, canonical_state: CanonicalStateDTO, tolerance: float = 0.0
    ) -> bool:
        ...

    @abstractmethod
    def integrate_with_kernel(
        self, canonical_state: CanonicalStateDTO, kernel: Any
    ) -> Any:
        ...

    @abstractmethod
    def handle_compliance_breach(
        self, error: Exception, context: dict[str, Any]
    ) -> Any:
        ...

    def is_initialized(self) -> bool:
        return False
