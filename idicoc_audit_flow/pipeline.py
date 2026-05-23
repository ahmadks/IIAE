from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from idicoc_core.core.graph.property_graph import PropertyGraph
from idicoc_core.runtime.config import RuntimeConfig
from idicoc_utils.hashing import canonical_json, sha256_hex
from idicoc_utils.logger import get_logger
from .base import CanonicalStateDTO, EntropyAnalyzer
from .config import AuditConfig
from .exceptions import WrapperInitializationError
from .kernel_client import KernelCustodyClient
from .axioms import AxiomEngine
from .strategies.mathematical import MathematicalDissonanceStrategy
from .strategies.semantic import SemanticDissonanceStrategy


class IIAEEnterpriseSDKWrapper:
    """Orquestador lineal del auditor que ejecuta cada etapa del pipeline."""

    def __init__(
        self,
        config: AuditConfig,
        entropy_analyzer: EntropyAnalyzer,
        axioms: Optional[List[Dict[str, Any]]] = None,
        aem_storage: Optional[Any] = None,
        ctm_storage: Optional[Any] = None,
    ) -> None:
        self.config = config
        self.entropy_analyzer = entropy_analyzer
        self.graph = PropertyGraph()
        self.axiom_engine = AxiomEngine(axioms)
        self.logger = get_logger("audit_flow.pipeline")

        if self.config.audit_mode == "semantic":
            self.dissonance_strategy = SemanticDissonanceStrategy(
                config=self.config,
            )
        else:
            self.dissonance_strategy = MathematicalDissonanceStrategy(
                config=self.config,
            )

        self.runtime_config = RuntimeConfig(
            constant_k=self.config.constant_k,
            entropy_analyzer=self.entropy_analyzer,
            property_graph=self.graph,
            rigidity_epsilon=self.config.rigidity_epsilon,
            delta_fp=self.config.isg_delta_fp,
            enable_hard_halt=self.config.enable_hard_halt,
            instance_name=self.config.source_name,
            aem_storage=aem_storage,
            ctm_storage=ctm_storage,
        )
        self.kernel_client = KernelCustodyClient(ctm=self.runtime_config.ctm) if self.config.ctm_mode == "full" else None
        self._initialized = False
        self.initialize()

    def initialize(self) -> None:
        self.axiom_engine.provision_graph(self.graph)
        self._initialized = True

    def admit(self, source_input: str) -> tuple[str, dict[str, Any]]:
        if not self._initialized:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        if source_input is None or not isinstance(source_input, str) or not source_input.strip():
            admission_metrics = {
                "entropy": 1.0,
                "category": "DISCARDED_NOISE",
                "admitted": False,
                "error": "Entrada vacía o nula",
                "structural": "",
                "noise": source_input,
            }
            return "", admission_metrics

        try:
            admitted_structure, admission_metrics = self.runtime_config.aem.admit(
                source_input,
                hard_halt_on_breach=False,
            )
        except Exception as exc:
            admission_metrics = {
                "entropy": 1.0,
                "category": "DISCARDED_NOISE",
                "admitted": False,
                "error": str(exc),
                "structural": "",
                "noise": source_input,
            }
            admitted_structure = ""

        return admitted_structure, admission_metrics

    def execute(
        self,
        source_input: str,
        context_input: Optional[List[str]] = None,
        context_axioms: Optional[List[str]] = None,
        epsilon_override: float | None = None,
    ) -> Dict[str, Any]:
        epsilon_used = epsilon_override if epsilon_override is not None else self.config.rigidity_epsilon

        try:
            admission_metrics: dict[str, Any] = {}
            admitted_input, admission_metrics = self.admit(source_input)

            if admitted_input is None or not isinstance(admitted_input, str):
                admitted_input = ""

            self.runtime_config.epsilon = epsilon_used

            policy_axioms = self.axiom_engine.render_axioms(self.graph)
            all_axioms = list(policy_axioms)
            if context_axioms:
                all_axioms.extend(context_axioms)
            context_chunks = context_input or []

            D_s, D_f, final_output, correction_flag, extra_metrics = self.dissonance_strategy.compute(
                source_input=source_input,
                context_input=context_chunks,
                context_axioms=all_axioms,
                epsilon=epsilon_used,
                validate_conflicts=self.config.validate_context_against_axioms,
            )

            timestamp = datetime.now(timezone.utc).isoformat()
            invariant_hash = sha256_hex(canonical_json(final_output))
            graph_hash = sha256_hex(canonical_json(self.graph.nodes))

            # Extraer d_logic de las métricas del modo activo (siempre presente tras la refactorización).
            d_logic = float(extra_metrics.get("d_logic", D_s))

            metadata = {
                "timestamp": timestamp,
                "d_s": D_s,
                "d_f": D_f,
                "audit_mode": self.config.audit_mode,
                "epsilon_used": epsilon_used,
                "epsilon": epsilon_used,
                "delta_fp": self.config.isg_delta_fp,
                "correction_flag": correction_flag,
                "admission_metrics": admission_metrics,
                "audit_metrics": extra_metrics,
                "admission_breach": None,
                "source_name": self.config.source_name,
                "invariant_state_hash": invariant_hash,
                "property_graph_hash": graph_hash,
                # Componentes coalgebraicos (Anexo J): D_s = λ_inv·d_inv + λ_logic·d_logic + λ_temporal·d_temporal
                "algebraic_components": {
                    "lambda_weights": [0.0, 1.0, 0.0],  # [λ_inv, λ_logic, λ_temporal]
                    "d_inv": 0.0,        # Sin acceso al estado latente V̂
                    "d_logic": d_logic,  # sup(max_geom_dist, max_nli_contradiction)
                    "d_temporal": 0.0,   # Reservado para extensión futura
                },
            }

            canonical_state = CanonicalStateDTO(
                data=final_output,
                metadata=metadata,
                source_axioms=all_axioms,
            )

            if self.config.ctm_mode == "full":
                kernel_factory = self.runtime_config.kernel_factory()
                kernel = kernel_factory()
                kernel_result = kernel.process(
                    canonical_state=canonical_state.data,
                    dissonance=D_s,
                    epsilon=epsilon_used,
                    property_graph=self.graph,
                    timestamp=metadata["timestamp"],
                )
                if kernel_result is None:
                    kernel_result = {
                        "status": "committed",
                        "root_hash": self.runtime_config.ctm.root_hash,
                    }

                receipt = self.kernel_client.commit(
                    canonical_state=canonical_state.data,
                    dissonance=D_s,
                    fact_dissonance=D_f,
                    epsilon=epsilon_used,
                    delta_fp=self.config.isg_delta_fp,
                    correction_flag=correction_flag,
                    source=self.config.source_name,
                    metadata=canonical_state.metadata,
                )
            elif self.config.ctm_mode == "log_only":
                self.logger.info(
                    "CTM Commit Log Only",
                    extra={
                        "iiae_data": {
                            "event": "commit",
                            "canonical_state": canonical_state.data,
                            "dissonance": D_s,
                            "fact_dissonance": D_f,
                            "epsilon": epsilon_used,
                            "correction_flag": correction_flag,
                            "source": self.config.source_name,
                            "metadata": canonical_state.metadata,
                        }
                    }
                )
                kernel_result = {"status": "log_only"}
                receipt = {"status": "log_only"}
            else:
                kernel_result = {"status": "disabled"}
                receipt = {"status": "disabled"}

            return {
                "canonical_state": canonical_state,
                "output": final_output,
                "kernel_result": kernel_result,
                "audit_receipt": receipt,
                "context_chunks": context_chunks,
            }
        except Exception as exc:
            timestamp = datetime.now(timezone.utc).isoformat()
            snapshot = {
                "event": "execute_pipeline_failure",
                "error": str(exc),
            }
            if self.config.ctm_mode == "full":
                self.runtime_config.ctm.seal_failure(snapshot, timestamp=timestamp)
            elif self.config.ctm_mode == "log_only":
                self.logger.error(
                    f"CTM Failure Log Only: {str(exc)}",
                    extra={"iiae_data": snapshot}
                )
            
            fallback_metadata = {
                "timestamp": timestamp,
                "d_s": 1.0,
                "d_f": 1.0,
                "audit_mode": self.config.audit_mode,
                "epsilon_used": epsilon_used,
                "epsilon": epsilon_used,
                "delta_fp": self.config.isg_delta_fp,
                "correction_flag": True,
                "admission_metrics": {},
                "audit_metrics": {"error": str(exc)},
                "admission_breach": None,
                "source_name": self.config.source_name,
                "invariant_state_hash": "",
                "property_graph_hash": "",
                "algebraic_components": {
                    "lambda_weights": [0.0, 1.0, 0.0],
                    "d_inv": 0.0,
                    "d_logic": 1.0,
                    "d_temporal": 0.0,
                },
            }
            fallback_state = CanonicalStateDTO(
                data=f"[CRITICAL WRAPPER ERROR] {str(exc)}",
                metadata=fallback_metadata,
                source_axioms=context_axioms or [],
            )
            return {
                "canonical_state": fallback_state,
                "output": f"[CRITICAL WRAPPER ERROR] {str(exc)}",
                "kernel_result": {"status": "failed", "error": str(exc)},
                "audit_receipt": {"status": "uncommitted", "error": str(exc)},
                "context_chunks": context_input or [],
            }
