"""
Paquete de auditoría IDICOC.

Exporta el auditor genérico, contratos y estrategias de disonancia.
"""

from __future__ import annotations

from .base import (
    CanonicalStateDTO,
    IIAENotaryContract,
)
from .config import AuditConfig
from .exceptions import ComplianceBreach, WrapperInitializationError
from .ctm_client import KernelCustodyClient
from .pipeline import IDICOCPipeline
from .axioms import AxiomEngine
from .dse import DissonanceStrategy
from .wrapper_pipeline import IDICOCNotaryClient
from .aem import AuditEntropyModule

__all__ = [
    "AuditConfig",
    "CanonicalStateDTO",
    "IIAENotaryContract",
    "AxiomEngine",
    "KernelCustodyClient",
    "IDICOCPipeline",
    "WrapperInitializationError",
    "ComplianceBreach",
    "IDICOCNotaryClient",
    "DissonanceStrategy",
    "AuditEntropyModule",
]
