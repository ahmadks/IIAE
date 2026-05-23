"""
Adaptador IDICOC entre la IA comercial y el núcleo determinista.

Este módulo ahora delega la orquestación completa al pipeline principal.
"""

from __future__ import annotations
from typing import Any

from idicoc_rag_wrapper.base import (
    CanonicalStateDTO,
    EntropyAnalyzer,
    IDICOCWrapperContract,
)
from idicoc_rag_wrapper.config import WrapperConfig
from idicoc_rag_wrapper.exceptions import ComplianceBreach, WrapperInitializationError
from idicoc_rag_wrapper.pipeline import IIAEEnterpriseSDKWrapper


class IDICOCWrapper(IDICOCWrapperContract):
    """Wrapper minimalista que adapta la API pública al pipeline de negocio."""

    def __init__(self, config: WrapperConfig, entropy_analyzer: EntropyAnalyzer) -> None:
        self.config = config
        self.entropy_analyzer = entropy_analyzer
        self.pipeline: IIAEEnterpriseSDKWrapper | None = None
        self._initialized = False
        self.initialize(config)

    def initialize(self, config: WrapperConfig) -> None:
        self.config = config
        self.pipeline = IIAEEnterpriseSDKWrapper(config, self.entropy_analyzer)
        self._initialized = True

    def adapt_input(self, ai_output: str, rag_context: dict[str, Any] | None = None) -> dict[str, Any]:
        texto = str(ai_output).strip()
        return {
            "text": texto,
            "rag_context": rag_context or {},
            "source": self.config.commercial_ai_name,
        }

    def admit(self, raw_input: Any) -> Any:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")
        return self.pipeline.admit(raw_input)

    def process(self, admitted_input: Any) -> CanonicalStateDTO:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        raw_value = admitted_input
        rag_context = None
        if isinstance(admitted_input, dict):
            raw_value = admitted_input.get("text", admitted_input)
            rag_context = admitted_input.get("rag_context")

        result = self.pipeline.execute(
            raw_input=raw_value,
            raw_output=raw_value,
            rag_context=rag_context if isinstance(rag_context, list) else None,
        )

        return result["canonical_state"]

    def process_interaction(
        self,
        user_prompt: str,
        ai_response: str,
        rag_context: list[str] | None = None,
    ) -> CanonicalStateDTO:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        result = self.pipeline.execute(
            raw_input=user_prompt,
            raw_output=ai_response,
            rag_context=rag_context,
        )
        return result["canonical_state"]

    def verify_compliance(self, canonical_state: CanonicalStateDTO, tolerance: float = 0.0) -> bool:
        if not canonical_state.verify_integrity():
            raise ComplianceBreach("Hash de integridad inválido", breach_type="integrity")

        umbral = tolerance if tolerance > 0.0 else self.config.rigidity_epsilon
        dissonance = float(canonical_state.metadata.get("d_s", 0.0))

        if dissonance > umbral:
            raise ComplianceBreach(
                "D_s excede el umbral de manifold",
                breach_type="dissonance",
                dissonance=dissonance,
                threshold=umbral,
            )

        return True

    def integrate_with_kernel(self, canonical_state: CanonicalStateDTO, kernel: Any) -> Any:
        if hasattr(kernel, "process"):
            kernel.process(canonical_state.data)
            return {
                "status": "kernel_processed",
                "root_hash": getattr(getattr(kernel, "ctm", None), "root_hash", None),
            }
        raise ComplianceBreach("El kernel no es compatible", breach_type="kernel_integration")

    def handle_compliance_breach(self, error: Exception, context: dict[str, Any]) -> Any:
        return {
            "error": str(error),
            "context": context,
        }

    def get_entropy_analyzer(self) -> EntropyAnalyzer:
        if self.entropy_analyzer is None:
            raise WrapperInitializationError("No hay analizador de entropía configurado.")
        return self.entropy_analyzer

    def is_initialized(self) -> bool:
        return self._initialized
