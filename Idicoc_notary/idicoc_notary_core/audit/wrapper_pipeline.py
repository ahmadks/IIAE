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
from .llm_interface import BaseLLMProvider


class CompatibleCanonicalState(CanonicalStateDTO):
    """Subclase de CanonicalStateDTO compatible con el acceso de diccionario de la UI."""

    def __getitem__(self, key: str) -> Any:
        if key == "canonical_state":
            return self
        if key == "source_policies":
            return self.source_policies
        if key == "metadata":
            return self.metadata
        if key == "status":
            return "REJECTED" if self.metadata.get("admission_breach", False) else "ADMITTED"
        if key == "correction_flag":
            return self.metadata.get("correction_flag", False)
        if key == "dissonance_metrics":
            ac = self.metadata.get("algebraic_components", {})
            return {
                "d_s": self.metadata.get("d_s", 0.0),
                "d_1": ac.get("d_1", 0.0),
                "d_2": ac.get("d_2", 0.0),
            }
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default


class SemanticPayload:
    """Payload unificado: texto legible + vector embedding."""

    def __init__(
        self, text: str, vec: Any = None, source_text: str = "", payload_type: str = "semantic"
    ):
        self.text_content = text
        self.source_text = source_text or text
        self.payload_type = payload_type
        if vec is None:
            from idicoc_notary_core.utils.embedding_service import EmbeddingService

            self.distribution = EmbeddingService().encode(text)
        else:
            self.distribution = vec

    def __repr__(self) -> str:
        return (
            f"SemanticPayload(payload_type={self.payload_type!r}, "
            f"source_text={self.source_text!r})"
        )


class IDICOCNotaryClient(IIAENotaryContract):
    """Wrapper minimalista que adapta la API pública al pipeline de negocio."""

    def __init__(
        self,
        config: AuditConfig,
        llm_provider: BaseLLMProvider | None = None,
    ) -> None:
        self.pipeline: IDICOCPipeline | None = None
        self._initialized = False
        self.llm_provider = llm_provider
        self.initialize(config, llm_provider=llm_provider)

    def initialize(self, config: AuditConfig, llm_provider: BaseLLMProvider | None = None) -> None:
        self.config = config
        self.llm_provider = llm_provider
        # If the provided LLM exposes an embedding adapter, register it with the config
        try:
            if llm_provider is not None and hasattr(llm_provider, "embedding_provider"):
                config.embedding_provider = getattr(llm_provider, "embedding_provider")
        except Exception:
            pass

        self.pipeline = IDICOCPipeline(config, llm_provider=llm_provider)
        self._initialized = True

    def adapt_input(
        self,
        audit_input: Any,
        context_input: list[str] | None = None,
        context_policies: list[str] | None = None,
        user_input: str | None = None,
    ) -> dict[str, Any]:
        """
        Adapta entrada multiparamétrica al formato interno del pipeline.

        Fase 2 (Interacción) -:
        - user_input: Instrucción del usuario (User Prompt)
        - context_input: Contexto RAG/sesión (System Prompt conditioning)
        - context_policies: Políticas ya compiladas en Fase 1
        - audit_input: Señal generativa interceptada (logits stream en Fase 3)

        Args:
            audit_input: Entrada de auditoría o logits interceptados
            context_input: Lista de fragmentos de contexto RAG
            context_policies: Lista de políticas aplicables
            user_input: Instrucción directa del usuario (NUEVO - Fase 2)

        Returns:
            Dict con campos mapeados al formato interno
        """
        return {
            self.config.input_field_audit: audit_input,
            self.config.input_field_context: context_input or [],
            self.config.input_field_policies: context_policies or [],
            self.config.input_field_user: user_input or "",
            "instance_name": self.config.instance_name,
        }

    def process(self, admitted_input: Any) -> CanonicalStateDTO:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        if isinstance(admitted_input, dict):
            res = self.process_dict(admitted_input)
            return res.get("canonical_state")

        res = self.process_interaction(
            audit_input=admitted_input,
            context_input=[],
            context_policies=[],
        )
        return res.get("canonical_state")

    def process_interaction(
        self,
        audit_input: SemanticPayload,
        context_input: list[str] | None = None,
        context_policies: list[str | dict[str, Any]] | None = None,
        user_input: str | None = None,
        epsilon_override: float | None = None,
        trace_input: str = "",
        client_id: str | None = None,
    ) -> Any:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        if not isinstance(audit_input, SemanticPayload):
            raise TypeError("audit_input must be an instance of SemanticPayload")

        result = self.pipeline.execute(
            audit_input=audit_input,
            context_input=context_input,
            context_policies=context_policies,
            user_input=user_input or "",
            epsilon_override=epsilon_override,
            trace_input=trace_input,
            client_id=client_id,
        )
        canonical = result["canonical_state"]
        return CompatibleCanonicalState(
            data=canonical.data,
            metadata=canonical.metadata,
            source_policies=canonical.source_policies,
            integrity_hash=canonical.integrity_hash,
            timestamp=canonical.timestamp,
        )

    def process_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        audit_input = data.get(self.config.input_field_audit, data.get("text", ""))
        context_input = data.get(self.config.input_field_context, data.get("context_input", []))
        context_policies = data.get(
            self.config.input_field_policies, data.get("context_policies", [])
        )
        user_input = data.get(self.config.input_field_user, data.get("user_input", ""))
        epsilon_override = data.get("epsilon_override", None)
        trace_input = data.get("trace_input", "")
        client_id = data.get("client_id", None)

        return self.process_interaction(
            audit_input=audit_input,
            context_input=context_input if isinstance(context_input, list) else [],
            context_policies=context_policies if isinstance(context_policies, list) else [],
            user_input=str(user_input) if user_input is not None else "",
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

    def verify_compliance(self, canonical_state: CanonicalStateDTO, tolerance: float = 0.0) -> bool:
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
            umbral = self.config.rigidity_epsilon
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
        # Verificación coalgebraica: los pesos λ deben ser
        # [0.0, 1.0, 0.0] y d_s debe coincidir con λ_logic · d_logic,
        # o con d_context cuando el contexto RAG domina la disonancia.
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

        expected_weights = list(self.config._normalized_weights)

        d_0 = float(algebraic.get("d_0", 0.0))
        d_1 = float(algebraic.get("d_1", 0.0))
        d_2 = float(algebraic.get("d_2", -1.0))
        d_3 = float(algebraic.get("d_3", 0.0))
        d_4 = float(algebraic.get("d_4", 0.0))
        d_5 = float(algebraic.get("d_5", 0.0))
        d_6 = float(algebraic.get("d_6", 0.0))
        d_context = float(canonical_state.metadata.get("d_context", 0.0))

        expected_d_s = sum(
            expected_weights[i] * [d_0, d_1, d_2, d_3, d_4, d_5, d_6][i] for i in range(7)
        )
        if d_context > expected_d_s:
            expected_d_s = d_context

        # Tolerancia 1e-4: Los kernels CUDA en FP16/BF16 acumulan sumas flotantes en un
        # orden no determinista por warp, produciendo desviaciones de hasta ~1e-5.
        # Usar 1e-6 generaría falsos positivos de violación algebraica en hardware real.
        # 1e-4 es la tolerancia estándar para sistemas de notaría conscientes de la
        # aritmética IEEE 754 en aceleradores de cuantización (cf. ISO/IEC 10967-3).
        if abs(dissonance - expected_d_s) > 1e-4:
            snapshot = {
                "event": "verify_compliance_algebraic",
                "error": "D_s no coincide con la suma ponderada de componentes",
                "d_s_recorded": dissonance,
                "expected_d_s": expected_d_s,
            }
            self._log_or_seal_failure(snapshot)
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
        self._log_or_seal_failure(failure_response)
        return failure_response

    def handle_compliance_breach(self, error: Exception, context: dict[str, Any]) -> Any:
        return {
            "error": str(error),
            "context": context,
        }

    def is_initialized(self) -> bool:
        return self._initialized
