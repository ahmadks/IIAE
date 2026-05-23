"""
Adaptador IDICOC entre la IA comercial y el núcleo determinista.

Este módulo solo contiene lógica de adaptación del input, validación ligera
y medición de disonancia D_s. No implementa modelos de lenguaje ni RAG.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any

from idicoc_core.runtime.config import RuntimeConfig
from idicoc_core.core.pipeline.kernel import CustodialKernel
from idicoc_rag_wrapper.base import (
    CanonicalStateDTO,
    EntropyAnalyzer,
    IDICOCWrapperContract,
)
from idicoc_rag_wrapper.config import WrapperConfig
from idicoc_rag_wrapper.exceptions import ComplianceBreach, WrapperInitializationError


class IDICOCWrapper(IDICOCWrapperContract):
    """Wrapper ligero que adapta la IA comercial al núcleo idicoc_core."""

    def __init__(self, config: WrapperConfig, entropy_analyzer: EntropyAnalyzer) -> None:
        self.config = config
        self.entropy_analyzer = entropy_analyzer
        self.kernel: CustodialKernel | None = None
        self._initialized = False
        self.initialize(config)

    def initialize(self, config: WrapperConfig) -> None:
        self.config = config
        self.kernel = self._create_kernel()
        self._initialized = True

    def _create_kernel(self) -> CustodialKernel:
        runtime_config = RuntimeConfig(
            constant_k=self.config.constant_k,
            entropy_analyzer=self.entropy_analyzer,
            mode=self.config.mode,
        )
        kernel_factory = runtime_config.kernel_factory()
        return kernel_factory()

    def adapt_input(self, ai_output: str, rag_context: dict[str, Any] | None = None) -> dict[str, Any]:
        texto = str(ai_output).strip()
        return {
            "text": texto,
            "rag_context": rag_context or {},
            "source": self.config.commercial_ai_name,
        }

    def admit(self, raw_input: Any) -> Any:
        if not self._initialized:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        if raw_input is None:
            raise ComplianceBreach("Entrada nula", breach_type="input_admission")

        if isinstance(raw_input, str) and not raw_input.strip():
            raise ComplianceBreach("Entrada vacía", breach_type="input_admission")

        if self.entropy_analyzer is None:
            raise WrapperInitializationError("No hay analizador de entropía configurado.")

        estructura, ruido = self.entropy_analyzer.decompose(raw_input)
        entropia = self.entropy_analyzer.measure_entropy(ruido if ruido is not None else raw_input)

        if entropia > self.config.epsilon_threshold:
            if self.entropy_analyzer.is_recoverable(ruido):
                raise ComplianceBreach(
                    "Ruido recuperable detectado",
                    breach_type="entropy_recoverable",
                    dissonance=entropia,
                    threshold=self.config.epsilon_threshold,
                )
            raise ComplianceBreach(
                "Ruido excesivo no recuperable",
                breach_type="entropy_rejection",
                dissonance=entropia,
                threshold=self.config.epsilon_threshold,
            )

        return estructura

    def process(self, admitted_input: Any) -> CanonicalStateDTO:
        rag_context = None
        raw_value = admitted_input

        if isinstance(admitted_input, dict):
            raw_value = admitted_input.get("text", admitted_input)
            rag_context = admitted_input.get("rag_context")

        admitted = self.admit(raw_value)
        adapted = self.adapt_input(admitted, rag_context)

        if self.kernel is None:
            self.kernel = self._create_kernel()

        self.kernel.process(adapted)

        dissonance = float(self.kernel.state_s["buffers"][4] or 0.0)
        epsilon = float(self.kernel.epsilon)
        root_hash = getattr(self.kernel.ctm, "root_hash", None)

        metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "dissonance": dissonance,
            "epsilon": epsilon,
            "root_hash": root_hash,
            "config_mode": self.config.mode,
            "source": self.config.commercial_ai_name,
            **self.config.extra_metadata,
        }

        canonical_state = CanonicalStateDTO(
            data=adapted,
            metadata=metadata,
            source_axioms=[],
        )

        return canonical_state

    def verify_compliance(self, canonical_state: CanonicalStateDTO, tolerance: float = 0.0) -> bool:
        if not canonical_state.verify_integrity():
            raise ComplianceBreach("Hash de integridad inválido", breach_type="integrity")

        umbral = tolerance if tolerance > 0.0 else self.config.epsilon_threshold
        dissonance = float(canonical_state.metadata.get("dissonance", 0.0))

        if dissonance > umbral:
            raise ComplianceBreach(
                "D_s excede el umbral",
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
            "timestamp": datetime.utcnow().isoformat(),
        }

    def get_entropy_analyzer(self) -> EntropyAnalyzer:
        if self.entropy_analyzer is None:
            raise WrapperInitializationError("No hay analizador de entropía configurado.")
        return self.entropy_analyzer

    def is_initialized(self) -> bool:
        return self._initialized
