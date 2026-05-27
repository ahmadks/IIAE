from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import numpy as np
from idicoc_notary_core.kernel.custody.merkle_dag import (
    CustodialTraceManager,
    EnvHardwareSealer,
    MerkleDAG,
)
from idicoc_notary_core.kernel.deviation.dqe import DissonanceCalculator
from idicoc_notary_core.kernel.dse.dse import AxiomExtractor
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
from .persistence.file_backend import FileCTMStorage
from .config import AuditConfig
from .exceptions import WrapperInitializationError
from .ctm_client import KernelCustodyClient
from .axioms import AxiomEngine
from .dse import (
    DissonanceStrategy as DissonanceStrategyProtocol,
    StructuralDissonanceStrategy,
)
from .aem import AuditEntropyModule


class IDICOCPipeline:
    """Orquestador lineal del auditor que ejecuta cada etapa del pipeline."""

    def __init__(
        self,
        config: AuditConfig,
        axioms: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.config = config
        self.graph = PropertyGraph()
        self.axiom_engine = AxiomEngine(axioms)
        self.logger = get_logger("audit_flow.pipeline")
        self.aem = AuditEntropyModule()

        self.anchor = SourceAnchor(np.zeros(1, dtype=float))

        ctm_storage = FileCTMStorage(
            self.config.ctm_nodes_path,
            self.config.ctm_root_path,
        )

        self.registry = ProjectionRegistry()
        self.isg = InvariantStateGenerator(
            anchor=self.anchor,
            registry=self.registry,
            delta_fp=self.config.isg_delta_fp,
        )
        self.verifier = InvariantVerifier(self.anchor)
        self.dse = AxiomExtractor(self.graph, self.config)
        self.dissonance_strategy = self._create_dissonance_strategy()
        self.dqe = DissonanceCalculator(
            strategy=self.dissonance_strategy,
            delta_fp=self.config.isg_delta_fp,
        )
        self.cmc = ManifoldConstructor(dqe=self.dqe)
        self.ctm = CustodialTraceManager(
            dag=MerkleDAG(
                sealer=EnvHardwareSealer(
                    key_env=self.config.hardware_key_env_var,
                    require_key=self.config.require_hardware_seal,
                ),
                storage_backend=ctm_storage,
            )
        )

        genesis_metadata = {
            "source_name": self.config.source_name,
            "ctm_mode": self.config.ctm_mode,
            "delta_fp": self.config.isg_delta_fp,
            "rigidity_epsilon": self.config.rigidity_epsilon,
            "lambda_weights": [
                self.dqe.lambda_0,
                self.dqe.lambda_1,
                self.dqe.lambda_2,
                self.dqe.lambda_3,
                self.dqe.lambda_4,
                self.dqe.lambda_5,
                self.dqe.lambda_6,
            ],
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
        self._initialized = False
        self.initialize()

    def _create_dissonance_strategy(self) -> DissonanceStrategyProtocol:
        return self.config.dissonance_strategy(config=self.config)

    def initialize(self) -> None:
        self.axiom_engine.provision_graph(self.graph)
        self._initialized = True

    def execute(
        self,
        audit_input: Any,
        context_input: Optional[List[str]] = None,
        context_axioms: Optional[List[str]] = None,
        epsilon_override: float | None = None,
        trace_input: str = "",
        client_id: str | None = None,
    ) -> Dict[str, Any]:
        epsilon_used = epsilon_override if epsilon_override is not None else self.config.rigidity_epsilon
        timestamp = datetime.now(timezone.utc).isoformat()

        # 1. Validación de entrada mínima
        if audit_input is None or (isinstance(audit_input, str) and not audit_input.strip()):
            return self._build_fallback_result(
                "empty_input", "Entrada vacía o nula", epsilon_used, trace_input, client_id, context_axioms, context_input
            )

        try:
            context_chunks = context_input or []
            policy_axioms = self.axiom_engine.render_axioms(self.graph)
            all_axioms = list(policy_axioms)
            if context_axioms:
                all_axioms.extend(context_axioms)

            # 2. ISG
            V_hat = self.isg.generate(audit_input)

            # 3. DSE
            self.dse.update_graph(
                raw_input=audit_input,
                canonical_state=V_hat,
                context_input=context_chunks,
                context_axioms=all_axioms,
            )

            # 4. CMC
            manifold = self.cmc.build(V_hat, self.graph, epsilon_used)

            # 5. DQE
            D_s = self.dqe.compute_dissonance(audit_input, V_hat, self.graph)

            admitted = False
            correction_flag = False
            y_corrected = audit_input
            D_f = 0.0

            if D_s <= epsilon_used:
                admitted = True
                y_corrected = audit_input
                correction_flag = False
            else:
                y_corrected = self.dqe.project_to_manifold(audit_input, manifold, V_hat, self.graph)
                D_s_corrected = self.dqe.compute_dissonance(y_corrected, V_hat, self.graph)
                if D_s_corrected <= epsilon_used:
                    admitted = True
                    correction_flag = True
                else:
                    admitted = False
                    correction_flag = False

            # Convertir ndarrays a listas de forma segura para toda la orquestación
            if isinstance(y_corrected, np.ndarray):
                y_corrected = y_corrected.tolist()
            elif hasattr(y_corrected, "distribution") and isinstance(y_corrected.distribution, np.ndarray):
                y_corrected = y_corrected.distribution.tolist()

            # 6. AEM
            aem_record = {
                "d_s": D_s,
                "d_f": D_f,
                "epsilon": epsilon_used,
                "correction_flag": correction_flag,
                "violated_axioms": [],
                "audit_input": str(audit_input) if isinstance(audit_input, np.ndarray) else audit_input,
                "timestamp": timestamp,
            }
            if admitted:
                self.aem.record_admission(aem_record)
            else:
                self.aem.record_rejection(aem_record)

            total_sigs, valid_sigs, rej_sigs = self.aem.get_counters()

            # 7. CTM
            v_hat_payload = getattr(V_hat, "measure_vector", getattr(V_hat, "data", V_hat))
            if isinstance(v_hat_payload, np.ndarray):
                v_hat_payload = v_hat_payload.tolist()
            invariant_hash = sha256_hex(canonical_json(v_hat_payload))
            graph_hash = sha256_hex(canonical_json(self.graph.nodes))

            d_logic = float(self.graph.evaluate(y_corrected)) if hasattr(self.graph, "evaluate") else 0.0

            metadata = {
                "timestamp": timestamp,
                "d_s": D_s,
                "d_f": D_f,
                "epsilon_used": epsilon_used,
                "epsilon": epsilon_used,
                "delta_fp": self.config.isg_delta_fp,
                "correction_flag": correction_flag,
                "admission_metrics": {
                    "admitted": admitted,
                    "structural": str(audit_input) if not correction_flag else y_corrected,
                },
                "audit_metrics": {"d_s": D_s, "d_logic": d_logic},
                "admission_breach": not admitted,
                "source_name": self.config.source_name,
                "client_id": client_id or self.config.client_id,
                "trace_input": trace_input or self.config.trace_input,
                "invariant_state_hash": invariant_hash,
                "property_graph_hash": graph_hash,
                "aem_counters": {
                    "total_signals": total_sigs,
                    "valid_signals": valid_sigs,
                    "rejected_signals": rej_sigs,
                },
                "algebraic_components": {
                    "d_0": 0.0,
                    "d_1": getattr(self.dissonance_strategy, "_d_inv_from_pair", lambda a, b: 0.0)(y_corrected, V_hat),
                    "d_2": d_logic,
                    "d_3": float(self.graph.compute_temporal(y_corrected)) if hasattr(self.graph, "compute_temporal") else 0.0,
                    "d_4": 0.0,
                    "d_5": 0.0,
                    "d_6": 0.0,
                }
            }
            metadata.update(self.config.extra_metadata)
            
            payload_data = y_corrected if admitted else "[REJECTED]"

            canonical_state = CanonicalStateDTO(
                data=payload_data,
                metadata=metadata,
                source_axioms=all_axioms,
            )

            kernel_result = {"status": "uncommitted"}
            receipt = {"status": "uncommitted"}

            if self.config.ctm_mode == "full":
                try:
                    self.ctm.commit(
                        canonical_state=y_corrected,
                        dissonance=D_s,
                        epsilon=epsilon_used,
                        property_graph=self.graph,
                        timestamp=timestamp,
                        invariant_state_hash=invariant_hash,
                        property_graph_hash=graph_hash,
                        aem_counters={
                            "total_signals": total_sigs,
                            "valid_signals": valid_sigs,
                            "rejected_signals": rej_sigs,
                        },
                    )
                    kernel_result = {
                        "status": "committed",
                        "root_hash": self.ctm.root_hash,
                    }
                    if self.kernel_client:
                        receipt = self.kernel_client.commit(
                            canonical_state=y_corrected,
                            dissonance=D_s,
                            fact_dissonance=0.0,
                            epsilon=epsilon_used,
                            delta_fp=self.config.isg_delta_fp,
                            correction_flag=correction_flag,
                            source=self.config.source_name,
                            metadata=metadata,
                        )
                    else:
                        receipt = kernel_result
                except Exception as exc:
                    self.logger.error("CTM commit failed", exc_info=exc)
                    kernel_result = {"status": "uncommitted", "error": str(exc)}
                    receipt = {"status": "uncommitted", "error": str(exc)}
            elif self.config.ctm_mode == "log_only":
                kernel_result = {"status": "log_only"}
                receipt = {"status": "log_only"}
            else:
                kernel_result = {"status": "disabled"}
                receipt = {"status": "disabled"}

            return {
                "canonical_state": canonical_state,
                "output": y_corrected if admitted else audit_input,
                "kernel_result": kernel_result,
                "audit_receipt": receipt,
                "context_chunks": context_chunks,
            }

        except Exception as exc:
            return self._build_fallback_result("failed", str(exc), epsilon_used, trace_input, client_id, context_axioms, context_input)

    def _build_fallback_result(
        self, status: str, reason: str, epsilon_used: float, trace_input: str, client_id: str | None, context_axioms: Optional[List[str]], context_input: Optional[List[str]]
    ) -> Dict[str, Any]:
        """Genera una respuesta segura de fallback en caso de error crónico o entrada inválida."""
        timestamp = datetime.now(timezone.utc).isoformat()
        fallback_metadata = {
            "timestamp": timestamp,
            "d_s": 1.0,
            "d_f": 1.0,
            "epsilon_used": epsilon_used,
            "epsilon": epsilon_used,
            "delta_fp": self.config.isg_delta_fp,
            "correction_flag": False,
            "admission_metrics": {"admitted": False, "error": reason},
            "audit_metrics": {"error": reason},
            "admission_breach": True,
            "source_name": self.config.source_name,
            "client_id": client_id or self.config.client_id,
            "trace_input": trace_input or self.config.trace_input,
            "invariant_state_hash": "",
            "property_graph_hash": "",
            "algebraic_components": {
                "d_0": 0.0,
                "d_1": 0.0,
                "d_2": 1.0,
                "d_3": 0.0,
                "d_4": 0.0,
                "d_5": 0.0,
                "d_6": 0.0,
            },
        }
        fallback_metadata.update(self.config.extra_metadata)
        fallback_state = CanonicalStateDTO(
            data=f"[ERROR] {reason}",
            metadata=fallback_metadata,
            source_axioms=context_axioms or [],
        )
        return {
            "canonical_state": fallback_state,
            "output": f"[ERROR] {reason}",
            "kernel_result": {"status": status, "error": reason},
            "audit_receipt": {"status": "uncommitted", "error": reason},
            "context_chunks": context_input or [],
        }
