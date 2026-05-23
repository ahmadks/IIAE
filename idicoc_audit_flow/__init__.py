"""
Paquete de auditoría IDICOC.

Exporta el auditor genérico, contratos y estrategias de disonancia.
"""

from __future__ import annotations

from .base import (
    BankEntropyAnalyzer,
    CanonicalStateDTO,
    EntropyAnalyzer,
    IDICOCWrapperContract,
)
from .config import AuditConfig
from .exceptions import ComplianceBreach, WrapperInitializationError
from .kernel_client import KernelCustodyClient
from .pipeline import IIAEEnterpriseSDKWrapper
from .axioms import AxiomEngine
from .strategies import MathematicalDissonanceStrategy, SemanticDissonanceStrategy
from .wrapper_pipeline import IDICOCWrapper

__all__ = [
    "AuditConfig",
    "CanonicalStateDTO",
    "EntropyAnalyzer",
    "IDICOCWrapperContract",
    "AxiomEngine",
    "KernelCustodyClient",
    "IIAEEnterpriseSDKWrapper",
    "WrapperInitializationError",
    "ComplianceBreach",
    "BankEntropyAnalyzer",
    "IDICOCWrapper",
    "SemanticDissonanceStrategy",
    "MathematicalDissonanceStrategy",
]
