"""
Adaptador IDICOC entre la IA comercial y el núcleo determinista.

Este módulo ahora delega la orquestación completa al pipeline principal.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any

from .base import (
    CanonicalStateDTO,
    EntropyAnalyzer,
    IDICOCWrapperContract,
)
from .config import AuditConfig
from .exceptions import WrapperInitializationError
from .pipeline import IIAEEnterpriseSDKWrapper


class IDICOCWrapper(IDICOCWrapperContract):
    """Wrapper minimalista que adapta la API pública al pipeline de negocio."""

    def __init__(self, config: AuditConfig, entropy_analyzer: EntropyAnalyzer) -> None:
        self.config = config
        self.entropy_analyzer = entropy_analyzer
        self.pipeline: IIAEEnterpriseSDKWrapper | None = None
        self._initialized = False
        self.initialize(config)

    def initialize(self, config: AuditConfig) -> None:
        self.config = config
        self.pipeline = IIAEEnterpriseSDKWrapper(config, self.entropy_analyzer)
        self._initialized = True

    def adapt_input(self, source_input: str, context_input: list[str] | None = None, context_axioms: list[str] | None = None) -> dict[str, Any]:
        return {
            self.config.input_field_source: str(source_input).strip(),
            self.config.input_field_context: context_input or [],
            self.config.input_field_axioms: context_axioms or [],
            "source_name": self.config.source_name,
        }

    def admit(self, source_input: Any) -> Any:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")
        return self.pipeline.admit(source_input)

    def process(self, admitted_input: Any) -> CanonicalStateDTO:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        if isinstance(admitted_input, dict):
            return self.process_dict(admitted_input)

        return self.process_interaction(
            source_input=str(admitted_input),
            context_input=[],
            context_axioms=[],
        )

    def process_interaction(
        self,
        source_input: str,
        context_input: list[str] | None = None,
        context_axioms: list[str] | None = None,
        mode: str | None = None,
        epsilon_override: float | None = None,
    ) -> CanonicalStateDTO:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        result = self.pipeline.execute(
            source_input=source_input,
            context_input=context_input,
            context_axioms=context_axioms,
            mode=mode,
            epsilon_override=epsilon_override,
        )
        return result["canonical_state"]

    def process_dict(self, data: dict[str, Any]) -> CanonicalStateDTO:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        source_input = data.get(self.config.input_field_source, data.get("text", ""))
        context_input = data.get(self.config.input_field_context, data.get("context_input", []))
        context_axioms = data.get(self.config.input_field_axioms, data.get("context_axioms", []))
        mode = data.get("mode", None)
        epsilon_override = data.get("epsilon_override", None)

        return self.process_interaction(
            source_input=str(source_input),
            context_input=context_input if isinstance(context_input, list) else [],
            context_axioms=context_axioms if isinstance(context_axioms, list) else [],
            mode=mode,
            epsilon_override=epsilon_override,
        )

    def verify_compliance(self, canonical_state: CanonicalStateDTO, tolerance: float = 0.0) -> bool:
        if not canonical_state.verify_integrity():
            snapshot = {
                "event": "verify_compliance",
                "error": "Hash de integridad inválido",
                "canonical_state": canonical_state.to_dict(),
            }
            if self.pipeline is not None:
                self.pipeline.runtime_config.ctm.seal_failure(
                    snapshot,
                    timestamp=datetime.utcnow().isoformat(),
                )
            return False

        umbral = tolerance if tolerance > 0.0 else self.config.rigidity_epsilon
        dissonance = float(canonical_state.metadata.get("d_s", 0.0))

        if dissonance > umbral:
            snapshot = {
                "event": "verify_compliance",
                "error": "D_s excede el umbral de manifold",
                "dissonance": dissonance,
                "threshold": umbral,
                "canonical_state": canonical_state.to_dict(),
            }
            if self.pipeline is not None:
                self.pipeline.runtime_config.ctm.seal_failure(
                    snapshot,
                    timestamp=datetime.utcnow().isoformat(),
                )
            return False

        # ---------------------------------------------------------------
        # Verificación coalgebraica (Anexo J): los pesos λ deben ser
        # [0.0, 1.0, 0.0] y d_s debe coincidir con λ_logic · d_logic.
        # Rol de notario: solo mide y registra, nunca bloquea.
        # ---------------------------------------------------------------
        algebraic = canonical_state.metadata.get("algebraic_components")
        if algebraic is None:
            snapshot = {
                "event": "verify_compliance_algebraic",
                "warning": "algebraic_components ausente en el estado canónico",
                "canonical_state": canonical_state.to_dict(),
            }
            if self.pipeline is not None:
                self.pipeline.runtime_config.ctm.seal_failure(
                    snapshot,
                    timestamp=datetime.utcnow().isoformat(),
                )
            return False

        expected_weights = [0.0, 1.0, 0.0]
        actual_weights = algebraic.get("lambda_weights", [])
        if actual_weights != expected_weights:
            snapshot = {
                "event": "verify_compliance_algebraic",
                "error": "Pesos coalgebraicos inválidos",
                "expected": expected_weights,
                "actual": actual_weights,
            }
            if self.pipeline is not None:
                self.pipeline.runtime_config.ctm.seal_failure(
                    snapshot,
                    timestamp=datetime.utcnow().isoformat(),
                )
            return False

        d_logic = float(algebraic.get("d_logic", -1.0))
        lambda_logic = float(expected_weights[1])
        expected_d_s = lambda_logic * d_logic
        if abs(dissonance - expected_d_s) > 1e-6:
            snapshot = {
                "event": "verify_compliance_algebraic",
                "error": "D_s no coincide con λ_logic · d_logic",
                "d_s_recorded": dissonance,
                "lambda_logic_times_d_logic": expected_d_s,
            }
            if self.pipeline is not None:
                self.pipeline.runtime_config.ctm.seal_failure(
                    snapshot,
                    timestamp=datetime.utcnow().isoformat(),
                )
            return False

        return True


    def integrate_with_kernel(self, canonical_state: CanonicalStateDTO, kernel: Any) -> Any:
        if hasattr(kernel, "process"):
            kernel.process(canonical_state.data)
            return {
                "status": "kernel_processed",
                "root_hash": getattr(getattr(kernel, "ctm", None), "root_hash", None),
            }

        failure_response = {
            "status": "kernel_integration_failed",
            "error": "El kernel no es compatible",
            "canonical_state": canonical_state.to_dict(),
        }
        if self.pipeline is not None:
            self.pipeline.runtime_config.ctm.seal_failure(
                failure_response,
                timestamp=datetime.utcnow().isoformat(),
            )
        return failure_response

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
