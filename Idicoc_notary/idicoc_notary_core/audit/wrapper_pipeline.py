"""
Adaptador IDICOC entre la IA comercial y el núcleo determinista.

Este módulo ahora delega la orquestación completa al pipeline principal.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional

from .base import (
    CanonicalStateDTO,
    IIAENotaryContract,
)
from .config import AuditConfig
from .exceptions import WrapperInitializationError
from .pipeline import IDICOCPipeline


class IDICOCNotaryClient(IIAENotaryContract):
    """Wrapper minimalista que adapta la API pública al pipeline de negocio."""

    def __init__(
        self,
        config: AuditConfig,
    ) -> None:
        self.config = config
        # Anchor is private to the wrapper; strategies should access it via
        # `self.get_terminal_reference()` or the configuration, not as a
        # public compute parameter.
        self._anchor: Any | None = None
        self.pipeline: IDICOCPipeline | None = None
        self._initialized = False
        self.initialize(config)

    def get_terminal_reference(self) -> Any:
        """Return the wrapper's terminal reference (private anchor or config).

        Strategies or callers may use this accessor to obtain the canonical
        reference for comparisons. Prefer configuration values when available.
        """
        if self._anchor is not None:
            return self._anchor
        return getattr(self.config, 'constant_k', None)

    def initialize(self, config: AuditConfig) -> None:
        self.config = config
        self.pipeline = IDICOCPipeline(config)
        self._initialized = True

    def adapt_input(
        self,
        audit_input: Any,
        context_input: list[str] | None = None,
        context_axioms: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            self.config.input_field_audit: audit_input,
            self.config.input_field_context: context_input or [],
            self.config.input_field_axioms: context_axioms or [],
            "instance_name": self.config.instance_name,
        }

    def process(self, admitted_input: Any) -> CanonicalStateDTO:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        if isinstance(admitted_input, dict):
            return self.process_dict(admitted_input)

        return self.process_interaction(
            audit_input=admitted_input,
            context_input=[],
            context_axioms=[],
        )

    def process_interaction(
        self,
        audit_input: Any,
        context_input: list[str] | None = None,
        context_axioms: list[str] | None = None,
        epsilon_override: float | None = None,
        trace_input: str = "",
        client_id: str | None = None,
    ) -> CanonicalStateDTO:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        result = self.pipeline.execute(
            audit_input=audit_input,
            context_input=context_input,
            context_axioms=context_axioms,
            epsilon_override=epsilon_override,
            trace_input=trace_input,
            client_id=client_id,
        )
        return result["canonical_state"]

    def process_dict(self, data: dict[str, Any]) -> CanonicalStateDTO:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        audit_input = data.get(self.config.input_field_audit, data.get("text", ""))
        context_input = data.get(
            self.config.input_field_context, data.get("context_input", [])
        )
        context_axioms = data.get(
            self.config.input_field_axioms, data.get("context_axioms", [])
        )
        epsilon_override = data.get("epsilon_override", None)
        trace_input = data.get("trace_input", "")
        client_id = data.get("client_id", None)

        return self.process_interaction(
            audit_input=audit_input,
            context_input=context_input if isinstance(context_input, list) else [],
            context_axioms=context_axioms if isinstance(context_axioms, list) else [],
            epsilon_override=epsilon_override,
            trace_input=str(trace_input) if trace_input is not None else "",
            client_id=str(client_id) if client_id is not None else None,
        )

    def _log_or_seal_failure(self, snapshot: dict[str, Any]) -> None:
        if self.pipeline is None:
            return
        if self.config.ctm_mode == "full":
            self.pipeline.ctm.seal_failure(
                snapshot,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        elif self.config.ctm_mode == "log_only":
            self.pipeline.logger.error(
                f"Compliance/Kernel Failure Log Only: {snapshot.get('error') or snapshot.get('warning') or 'unknown error'}",
                extra={"iiae_data": snapshot},
            )

    def verify_compliance(
        self, canonical_state: CanonicalStateDTO, tolerance: float = 0.0
    ) -> bool:
        snapshot: dict[str, Any]
        if not canonical_state.verify_integrity():
            snapshot = {
                "event": "verify_compliance",
                "error": "Hash de integridad inválido",
                "canonical_state": canonical_state.to_dict(),
            }
            self._log_or_seal_failure(snapshot)
            return False

        if tolerance and tolerance > 0.0:
            umbral = tolerance
        else:
            # Allow a small slack derived from correction_base_tolerance (capped at 0.1)
            umbral = self.config.rigidity_epsilon + min(self.config.correction_base_tolerance, 0.1)
        dissonance = float(canonical_state.metadata.get("d_s", 0.0))

        if dissonance > umbral:
            snapshot = {
                "event": "verify_compliance",
                "error": "D_s excede el umbral de manifold",
                "dissonance": dissonance,
                "threshold": umbral,
                "canonical_state": canonical_state.to_dict(),
            }
            self._log_or_seal_failure(snapshot)
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
            self._log_or_seal_failure(snapshot)
            return False

        expected_weights = list(self.config.dissonance_weights)

        d_0 = float(algebraic.get("d_0", 0.0))
        d_1 = float(algebraic.get("d_1", 0.0))
        d_2 = float(algebraic.get("d_2", -1.0))
        d_3 = float(algebraic.get("d_3", 0.0))
        d_4 = float(algebraic.get("d_4", 0.0))
        d_5 = float(algebraic.get("d_5", 0.0))
        d_6 = float(algebraic.get("d_6", 0.0))
        
        expected_d_s = sum(
            expected_weights[i] * [d_0, d_1, d_2, d_3, d_4, d_5, d_6][i]
            for i in range(7)
        )
        print(f"DEBUG: expected_weights={expected_weights}, D_s={dissonance}, expected_d_s={expected_d_s}")
        if abs(dissonance - expected_d_s) > 1e-6:
            snapshot = {
                "event": "verify_compliance_algebraic",
                "error": "D_s no coincide con la suma ponderada de componentes",
                "d_s_recorded": dissonance,
                "expected_d_s": expected_d_s,
            }
            self._log_or_seal_failure(snapshot)
            return False

        return True

    def integrate_with_kernel(
        self, canonical_state: CanonicalStateDTO, kernel: Any
    ) -> Any:
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
        self._log_or_seal_failure(failure_response)
        return failure_response

    def handle_compliance_breach(
        self, error: Exception, context: dict[str, Any]
    ) -> Any:
        return {
            "error": str(error),
            "context": context,
        }

    def is_initialized(self) -> bool:
        return self._initialized
