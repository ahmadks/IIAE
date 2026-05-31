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


class IDICOCNotaryClient(IIAENotaryContract):
    """Wrapper minimalista que adapta la API pública al pipeline de negocio."""

    def __init__(
        self,
        config: AuditConfig,
    ) -> None:
        self.pipeline: IDICOCPipeline | None = None
        self._initialized = False
        self.initialize(config)

    def initialize(self, config: AuditConfig) -> None:
        self.config = config
        self.pipeline = IDICOCPipeline(config)
        self._initialized = True

    def adapt_input(
        self,
        audit_input: Any,
        context_input: list[str] | None = None,
        context_policies: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            self.config.input_field_audit: audit_input,
            self.config.input_field_context: context_input or [],
            self.config.input_field_policies: context_policies or [],
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
        audit_input: Any,
        context_input: list[str] | None = None,
        context_policies: list[str | dict[str, Any]] | None = None,
        epsilon_override: float | None = None,
        trace_input: str = "",
        client_id: str | None = None,
    ) -> Any:
        if not self._initialized or self.pipeline is None:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        # ── Normalización Universal al Espacio Semántico ──────────────────────
        # IDICOC opera SIEMPRE en un único espacio semántico unificado (384D).
        # Cualquier entrada — string, ndarray, lista, dict, escalar — se convierte
        # primero a una descripción textual y luego a un embedding vectorial.
        # Esto garantiza coherencia dimensional con:
        #   · El ancla K (Axioma de Unicidad, ~384D)
        #   · Los embeddings de las políticas del PropertyGraph (~384D)
        #   · Los embeddings del contexto RAG (~384D)
        # La comparación d_1 (EMD a K), d_2 (Policy Graph) y d_3 (bisimulación)
        # trabajan así en el mismo espacio de Hilbert, sin incompatibilidades.
        import numpy as np
        from idicoc_notary_core.utils.embedding_service import EmbeddingService

        class SemanticPayload:
            """Payload unificado: texto legible + vector embedding."""
            def __init__(self, text: str, vec: "np.ndarray"):
                self.text_content = text
                self.distribution = vec

        def _to_text(inp: Any) -> str:
            """Serializa cualquier tipo de entrada a texto descriptivo en español."""
            # Ya es un string
            if isinstance(inp, str):
                return inp
            # Dict con campo 'text'
            if isinstance(inp, dict) and "text" in inp:
                return str(inp["text"])
            # Ya tiene text_content (SemanticPayload previo)
            if hasattr(inp, "text_content") and inp.text_content:
                return str(inp.text_content)
            # Array o lista numérica → descripción de distribución
            try:
                arr = np.asarray(inp, dtype=float).flatten()
                if arr.ndim == 1 and arr.size > 0:
                    s = arr.sum()
                    dist = arr / s if s > 1e-12 else arr
                    dominant = int(np.argmax(dist))
                    entropy = float(-np.sum(dist * np.log(dist + 1e-12)))
                    desc = ", ".join(f"dim{i}={v:.6f}" for i, v in enumerate(dist))
                    balance = "equilibrada" if float(dist.max()) < 0.4 else "sesgada"
                    return (
                        f"Señal vectorial de auditoría [{arr.size}D]: [{desc}]. "
                        f"Distribución {balance}. Dimensión dominante: dim{dominant} "
                        f"({float(dist[dominant]):.6f}). Entropía: {entropy:.6f}."
                    )
            except (TypeError, ValueError):
                pass
            # Fallback genérico
            return f"Entrada de auditoría: {str(inp)}"

        text_val = _to_text(audit_input)
        try:
            vec = EmbeddingService().encode(text_val)
            audit_input = SemanticPayload(text_val, vec)
        except Exception as e:
            self.pipeline.logger.warning(
                f"Error codificando audit_input al espacio semántico: {e}. "
                "Se enviará el texto sin embedding."
            )
            audit_input = text_val  # fallback: al menos el texto

        result = self.pipeline.execute(
            audit_input=audit_input,
            context_input=context_input,
            context_policies=context_policies,
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
        context_policies = data.get(self.config.input_field_policies, data.get("context_policies", []))
        epsilon_override = data.get("epsilon_override", None)
        trace_input = data.get("trace_input", "")
        client_id = data.get("client_id", None)

        return self.process_interaction(
            audit_input=audit_input,
            context_input=context_input if isinstance(context_input, list) else [],
            context_policies=context_policies if isinstance(context_policies, list) else [],
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
        # Verificación coalgebraica: los pesos λ deben ser
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

        expected_weights = list(self.config._normalized_weights)

        d_0 = float(algebraic.get("d_0", 0.0))
        d_1 = float(algebraic.get("d_1", 0.0))
        d_2 = float(algebraic.get("d_2", -1.0))
        d_3 = float(algebraic.get("d_3", 0.0))
        d_4 = float(algebraic.get("d_4", 0.0))
        d_5 = float(algebraic.get("d_5", 0.0))
        d_6 = float(algebraic.get("d_6", 0.0))

        expected_d_s = sum(
            expected_weights[i] * [d_0, d_1, d_2, d_3, d_4, d_5, d_6][i] for i in range(7)
        )
        print(
            f"DEBUG: expected_weights={expected_weights}, D_s={dissonance}, expected_d_s={expected_d_s}"
        )
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
