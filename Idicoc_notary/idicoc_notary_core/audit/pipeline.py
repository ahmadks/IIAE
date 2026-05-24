from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from idicoc_notary_core.kernel.admission.aem import AnomalousEventManager
from idicoc_notary_core.kernel.custody.merkle_dag import (
    CustodialTraceManager,
    EnvHardwareSealer,
    MerkleDAG,
)
from idicoc_notary_core.kernel.deviation.dqe import DeviationQuantifier
from idicoc_notary_core.kernel.dse.dse import DynamicSchemaExtractor
from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph
from idicoc_notary_core.kernel.manifold.cmc import ManifoldConstructor
from idicoc_notary_core.kernel.pipeline.kernel import CustodialKernel
from idicoc_notary_core.kernel.projection.invariant_state_generator import InvariantStateGenerator
from idicoc_notary_core.kernel.source.anchor import SourceAnchor
from idicoc_notary_core.kernel.verification.registry import ProjectionRegistry
from idicoc_notary_core.kernel.verification.verifier import InvariantVerifier
from idicoc_notary_core.utils.hashing import canonical_json, sha256_hex
from idicoc_notary_core.utils.logger import get_logger

from .base import CanonicalStateDTO
from idicoc_notary_core.kernel.admission.aem import EntropyAnalyzer
from .config import AuditConfig
from .exceptions import WrapperInitializationError
from .kernel_client import KernelCustodyClient
from .axioms import AxiomEngine
from .strategies.semantic import SemanticDissonanceStrategy


class IIAEServiceAuditor:
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

        self.anchor = SourceAnchor(self.config.constant_k)
        self.aem = AnomalousEventManager(
            property_graph=self.graph,
            analyzer=self.entropy_analyzer,
            threshold=0.85,
            instance_name=self.config.source_name,
            storage_backend=aem_storage,
        )
        self.registry = ProjectionRegistry()
        self.isg = InvariantStateGenerator(
            anchor=self.anchor,
            registry=self.registry,
            delta_fp=self.config.isg_delta_fp,
        )
        self.verifier = InvariantVerifier(self.anchor)
        self.dse = DynamicSchemaExtractor(self.graph)
        self.dqe = DeviationQuantifier(delta_fp=self.config.isg_delta_fp)
        self.cmc = ManifoldConstructor(dqe=self.dqe)
        self.ctm = CustodialTraceManager(
            dag=MerkleDAG(
                sealer=EnvHardwareSealer(),
                storage_backend=ctm_storage,
            )
        )

        genesis_metadata = {
            "source_name": self.config.source_name,
            "ctm_mode": self.config.ctm_mode,
            "delta_fp": self.config.isg_delta_fp,
            "rigidity_epsilon": self.config.rigidity_epsilon,
            "lambda_weights": (
                self.dqe.lambda_inv,
                self.dqe.lambda_logic,
                self.dqe.lambda_temporal,
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.ctm.initialize_genesis(
            genesis_metadata,
            timestamp=genesis_metadata["timestamp"],
        )

        self.kernel_client = (
            KernelCustodyClient(ctm=self.ctm)
            if self.config.ctm_mode == "full"
            else None
        )
        self.dissonance_strategy = self._create_dissonance_strategy()
        self._initialized = False
        self.initialize()

    def _create_dissonance_strategy(self) -> Any:
        return SemanticDissonanceStrategy(config=self.config)

    def initialize(self) -> None:
        self.axiom_engine.provision_graph(self.graph)
        self._initialized = True

    def _make_kernel_factory(self) -> Callable[[], CustodialKernel]:
        def _factory() -> CustodialKernel:
            return CustodialKernel(
                aem=self.aem,
                isg=self.isg,
                verifier=self.verifier,
                ctm=self.ctm,
                dse=self.dse,
                cmc=self.cmc,
                dqe=self.dqe,
                epsilon=self.config.rigidity_epsilon,
                enable_hard_halt=self.config.enable_hard_halt,
            )

        return _factory

    def admit(self, audit_input: str) -> tuple[str, dict[str, Any]]:
        if not self._initialized:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        if audit_input is None or not isinstance(audit_input, str) or not audit_input.strip():
            admission_metrics = {
                "entropy": 1.0,
                "category": "DISCARDED_NOISE",
                "admitted": False,
                "error": "Entrada vacía o nula",
                "structural": "",
                "noise": audit_input,
            }
            return "", admission_metrics

        try:
            admitted_structure, admission_metrics = self.aem.admit(
                audit_input,
                hard_halt_on_breach=False,
            )
        except Exception as exc:
            admission_metrics = {
                "entropy": 1.0,
                "category": "DISCARDED_NOISE",
                "admitted": False,
                "error": str(exc),
                "structural": "",
                "noise": audit_input,
            }
            admitted_structure = ""

        return admitted_structure, admission_metrics

    def execute(
        self,
        audit_input: str,
        context_input: Optional[List[str]] = None,
        context_axioms: Optional[List[str]] = None,
        epsilon_override: float | None = None,
        trace_input: str = "",
        client_id: str | None = None,
    ) -> Dict[str, Any]:
        epsilon_used = epsilon_override if epsilon_override is not None else self.config.rigidity_epsilon

        try:
            admission_metrics: dict[str, Any] = {}
            admitted_input, admission_metrics = self.admit(audit_input)

            if admitted_input is None or not isinstance(admitted_input, str):
                admitted_input = ""

            policy_axioms = self.axiom_engine.render_axioms(self.graph)
            all_axioms = list(policy_axioms)
            if context_axioms:
                all_axioms.extend(context_axioms)
            context_chunks = context_input or []

            D_s, D_f, final_output, correction_flag, extra_metrics = self.dissonance_strategy.compute(
                audit_input=audit_input,
                context_input=context_chunks,
                context_axioms=all_axioms,
                epsilon=epsilon_used,
                validate_conflicts=self.config.validate_context_against_axioms,
            )

            timestamp = datetime.now(timezone.utc).isoformat()
            invariant_hash = sha256_hex(canonical_json(final_output))
            graph_hash = sha256_hex(canonical_json(self.graph.nodes))
            d_logic = float(extra_metrics.get("d_logic", D_s))

            metadata = {
                "timestamp": timestamp,
                "d_s": D_s,
                "d_f": D_f,
                "epsilon_used": epsilon_used,
                "epsilon": epsilon_used,
                "delta_fp": self.config.isg_delta_fp,
                "correction_flag": correction_flag,
                "admission_metrics": admission_metrics,
                "audit_metrics": extra_metrics,
                "admission_breach": None,
                "source_name": self.config.source_name,
                "client_id": client_id or self.config.client_id,
                "trace_input": trace_input or self.config.trace_input,
                "invariant_state_hash": invariant_hash,
                "property_graph_hash": graph_hash,
                "algebraic_components": {
                    "lambda_weights": [0.0, 1.0, 0.0],
                    "d_inv": 0.0,
                    "d_logic": d_logic,
                    "d_temporal": 0.0,
                },
            }
            metadata.update(self.config.extra_metadata)

            canonical_state = CanonicalStateDTO(
                data=final_output,
                metadata=metadata,
                source_axioms=all_axioms,
            )

            if self.config.ctm_mode == "full":
                kernel_factory = self._make_kernel_factory()
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
                        "root_hash": self.ctm.root_hash,
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
                    },
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
                self.ctm.seal_failure(snapshot, timestamp=timestamp)
            elif self.config.ctm_mode == "log_only":
                self.logger.error(
                    f"CTM Failure Log Only: {str(exc)}",
                    extra={"iiae_data": snapshot},
                )

            fallback_metadata = {
                "timestamp": timestamp,
                "d_s": 1.0,
                "d_f": 1.0,
                "epsilon_used": epsilon_used,
                "epsilon": epsilon_used,
                "delta_fp": self.config.isg_delta_fp,
                "correction_flag": True,
                "admission_metrics": {},
                "audit_metrics": {"error": str(exc)},
                "admission_breach": None,
                "source_name": self.config.source_name,
                "client_id": client_id or self.config.client_id,
                "trace_input": trace_input or self.config.trace_input,
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
