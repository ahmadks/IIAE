"""IDICOC Notary SDK core kernel package.

Exporta los componentes internos del kernel para acceso directo
desde `idicoc_notary_core.kernel`.

Nota: InvariantVerifier se carga de forma diferida para evitar el ciclo
circular entre los paquetes `projection` y `verification`.
"""

from __future__ import annotations

from .custody import (
    HardwareSealer,
    CTMStorageBackend,
    NoOpHardwareSealer,
    EnvHardwareSealer,
    MerkleNode,
    MerkleDAG,
    CustodialTraceManager,
)
from .dse import PolicyExtractor
from .exceptions import AlignmentBreach, InvariantStateBreach, HardHaltException
from .graph import PropertyGraph
from .manifold import ManifoldConstructor
from .pipeline import CustodialKernel
from .projection import CanonicalState, InvariantStateGenerator
from .verification import ProjectionRegistry  # InvariantVerifier se carga diferidamente

__all__ = [
    # Custody
    "HardwareSealer",
    "CTMStorageBackend",
    "NoOpHardwareSealer",
    "EnvHardwareSealer",
    "MerkleNode",
    "MerkleDAG",
    "CustodialTraceManager",
    # DSE
    "PolicyExtractor",
    # Exceptions
    "AlignmentBreach",
    "InvariantStateBreach",
    "HardHaltException",
    # Graph
    "PropertyGraph",
    # Manifold
    "ManifoldConstructor",
    # Pipeline
    "CustodialKernel",
    # Projection
    "CanonicalState",
    "InvariantStateGenerator",
    # Verification
    "InvariantVerifier",
    "ProjectionRegistry",
]


def __getattr__(name: str) -> object:
    if name == "InvariantVerifier":
        from .verification.verifier import InvariantVerifier  # noqa: PLC0415
        return InvariantVerifier
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
