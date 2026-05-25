"""
Paquete de auditoría IDICOC.

Exporta el auditor genérico, contratos y estrategias de disonancia.
"""

from __future__ import annotations

from .base import (
    CanonicalStateDTO,
    IIAENotaryContract,
)
from idicoc_notary_core.kernel.admission.aem import EntropyAnalyzer
from .config import AuditConfig
from .exceptions import ComplianceBreach, WrapperInitializationError
from .kernel_client import KernelCustodyClient
from .pipeline import IIAEServiceAuditor
from .axioms import AxiomEngine
from .dse import DissonanceStrategy
from .wrapper_pipeline import IIAEService

__all__ = [
    "AuditConfig",
    "CanonicalStateDTO",
    "EntropyAnalyzer",
    "IIAENotaryContract",
    "AxiomEngine",
    "KernelCustodyClient",
    "IIAEServiceAuditor",
    "WrapperInitializationError",
    "ComplianceBreach",
    "IIAEService",
    "DissonanceStrategy",
]
