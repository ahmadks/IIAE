"""
Paquete de auditoría IDICOC.

Exporta el auditor genérico, contratos y estrategias de disonancia.
"""

from __future__ import annotations

from .base import (
    BankEntropyAnalyzer,
    CanonicalStateDTO,
    EntropyAnalyzer,
    IIAENotaryContract,
)
from .config import AuditConfig
from .exceptions import ComplianceBreach, WrapperInitializationError
from .kernel_client import KernelCustodyClient
from .pipeline import IIAEServiceAuditor
from .axioms import AxiomEngine
from .strategies import MathematicalDissonanceStrategy, SemanticDissonanceStrategy
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
    "BankEntropyAnalyzer",
    "IIAEService",
    "SemanticDissonanceStrategy",
    "MathematicalDissonanceStrategy",
]
