"""
Wrapper ligero IDICOC.

Exporta solo la lógica necesaria para adaptar la IA comercial al núcleo.
"""

from __future__ import annotations

from idicoc_rag_wrapper.base import (
    CanonicalStateDTO,
    EntropyAnalyzer,
    IDICOCWrapperContract,
)
from idicoc_rag_wrapper.config import WrapperConfig
from idicoc_rag_wrapper.dqe_formal import DQEEngineFormal
from idicoc_rag_wrapper.exceptions import ComplianceBreach, WrapperInitializationError
from idicoc_rag_wrapper.kernel_client import KernelCustodyClient
from idicoc_rag_wrapper.pipeline import IIAEEnterpriseSDKWrapper
from idicoc_rag_wrapper.policy import PolicyEngine
from idicoc_rag_wrapper.rag_gateway import MiniRAGEngine
from idicoc_rag_wrapper.wrapper_pipeline import IDICOCWrapper

__all__ = [
    "CanonicalStateDTO",
    "EntropyAnalyzer",
    "IDICOCWrapperContract",
    "WrapperConfig",
    "DQEEngineFormal",
    "PolicyEngine",
    "MiniRAGEngine",
    "KernelCustodyClient",
    "IIAEEnterpriseSDKWrapper",
    "WrapperInitializationError",
    "ComplianceBreach",
    "IDICOCWrapper",
]
