from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional

from idicoc_core.core.graph.property_graph import PropertyGraph
from idicoc_core.runtime.config import RuntimeConfig
from idicoc_core.util.hashing import canonical_json, sha256_hex
from idicoc_rag_wrapper.base import CanonicalStateDTO, EntropyAnalyzer
from idicoc_rag_wrapper.config import WrapperConfig
from idicoc_rag_wrapper.dqe_formal import DQEEngineFormal
from idicoc_rag_wrapper.exceptions import ComplianceBreach, WrapperInitializationError
from idicoc_rag_wrapper.kernel_client import KernelCustodyClient
from idicoc_rag_wrapper.policy import PolicyEngine
from idicoc_rag_wrapper.rag_gateway import MiniRAGEngine


class IIAEEnterpriseSDKWrapper:
    """Orquestador lineal del wrapper que ejecuta cada etapa del pipeline."""

    def __init__(
        self,
        config: WrapperConfig,
        entropy_analyzer: EntropyAnalyzer,
        policy_axioms: Optional[List[Dict[str, Any]]] = None,
        rag_corpus: Optional[List[str]] = None,
    ) -> None:
        self.config = config
        self.entropy_analyzer = entropy_analyzer
        self.graph = PropertyGraph()
        self.policy_engine = PolicyEngine(policy_axioms)
        self.rag_engine = MiniRAGEngine(
            embedding_model_name=self.config.embedding_model_name,
            corpus=rag_corpus or [],
        )
        self.dqe_engine = DQEEngineFormal(
            embedding_model_name=self.config.embedding_model_name,
            nli_model_name=self.config.nli_model_name,
            delta_fp=self.config.delta_fp,
        )
        self.runtime_config = RuntimeConfig(
            constant_k=self.config.constant_k,
            entropy_analyzer=self.entropy_analyzer,
            property_graph=self.graph,
            mode="factual",
            rigidity_epsilon=self.config.rigidity_epsilon,
            delta_fp=self.config.delta_fp,
        )
        self.kernel_client = KernelCustodyClient(ctm=self.runtime_config.ctm)
        self._initialized = False
        self.initialize()

    def initialize(self) -> None:
        self.policy_engine.provision_graph(self.graph)
        self._initialized = True

    def admit(self, raw_input: str) -> tuple[str, dict[str, Any]]:
        if not self._initialized:
            raise WrapperInitializationError("El wrapper no está inicializado.")

        if raw_input is None or not isinstance(raw_input, str) or not raw_input.strip():
            raise ComplianceBreach("Entrada no válida para admisión.", breach_type="input_admission")

        admitted_structure, admission_metrics = self.runtime_config.aem.admit(
            raw_input,
            hard_halt_on_breach=self.config.enable_hard_halt,
        )

        return admitted_structure, admission_metrics

    def execute(
        self,
        raw_input: str,
        raw_output: str,
        rag_context: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        admission_metrics: dict[str, Any] = {}
        admitted_input, admission_metrics = self.admit(raw_input)

        if admitted_input is None or not isinstance(admitted_input, str):
            admitted_input = ""

        if rag_context is not None:
            self.rag_engine.index_corpus(rag_context)

        axioms = self.policy_engine.render_axioms(self.graph)
        rag_chunks = self.rag_engine.retrieve(
            raw_output,
            top_k=self.config.max_rag_results,
            min_score=self.config.min_rag_score,
        )

        D_s, D_f, final_output, correction_flag = self.dqe_engine.quantify_dissonance(
            raw_response=raw_output,
            axioms=axioms,
            rag_chunks=rag_chunks,
            epsilon=self.config.rigidity_epsilon,
        )

        metadata = {
            "timestamp": datetime.utcnow().isoformat(),
            "d_s": D_s,
            "d_f": D_f,
            "epsilon": self.config.rigidity_epsilon,
            "delta_fp": self.config.delta_fp,
            "correction_flag": correction_flag,
            "admission_metrics": admission_metrics,
            "admission_breach": None,
            "source": self.config.commercial_ai_name,
        }

        canonical_state = CanonicalStateDTO(
            data=final_output,
            metadata=metadata,
            source_axioms=axioms,
        )

        invariant_hash = sha256_hex(canonical_json(canonical_state.data))
        graph_hash = sha256_hex(canonical_json(self.graph.nodes))
        canonical_state.metadata["invariant_state_hash"] = invariant_hash
        canonical_state.metadata["property_graph_hash"] = graph_hash

        kernel_factory = self.runtime_config.kernel_factory()
        kernel = kernel_factory()
        kernel_result = kernel.process(
            canonical_state=canonical_state.data,
            dissonance=D_s,
            epsilon=self.config.rigidity_epsilon,
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
            epsilon=self.config.rigidity_epsilon,
            delta_fp=self.config.delta_fp,
            correction_flag=correction_flag,
            source=self.config.commercial_ai_name,
            metadata=canonical_state.metadata,
        )

        return {
            "canonical_state": canonical_state,
            "output": final_output,
            "kernel_result": kernel_result,
            "audit_receipt": receipt,
            "rag_chunks": rag_chunks,
        }
