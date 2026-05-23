from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, List, Optional

from idicoc_core.core.graph.property_graph import PropertyGraph
from idicoc_core.runtime.config import RuntimeConfig
from idicoc_utils.hashing import canonical_json, sha256_hex
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
    ) -> None:
        self.config = config
        self.entropy_analyzer = entropy_analyzer
        self.graph = PropertyGraph()
        self.axiom_engine = AxiomEngine(axioms)

        if self.config.audit_mode == "semantic":
            self.dissonance_strategy = SemanticDissonanceStrategy(
                embedding_model_name=self.config.semantic_embedding_model,
                nli_model_name=self.config.semantic_nli_model,
                delta_fp=self.config.delta_fp,
            )
        else:
            embedder = None
            if self.config.mathematical_embedding_model:
                from sentence_transformers import SentenceTransformer

                embedder = SentenceTransformer(self.config.mathematical_embedding_model)
            self.dissonance_strategy = MathematicalDissonanceStrategy(
                weights=self.config.mathematical_weights,
                delta_fp=self.config.mathematical_delta_fp,
                embedding_model=embedder,
            )

        self.runtime_config = RuntimeConfig(
            constant_k=self.config.constant_k,
            entropy_analyzer=self.entropy_analyzer,
            property_graph=self.graph,
            mode="factual",
            rigidity_epsilon=self.config.rigidity_epsilon,
            delta_fp=self.config.delta_fp,
            enable_hard_halt=self.config.enable_hard_halt,
        )
        self.kernel_client = KernelCustodyClient(ctm=self.runtime_config.ctm)
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
        mode: str = "factual",
        epsilon_override: float | None = None,
    ) -> Dict[str, Any]:
        admission_metrics: dict[str, Any] = {}
        admitted_input, admission_metrics = self.admit(source_input)

        if admitted_input is None or not isinstance(admitted_input, str):
            admitted_input = ""

        epsilon_used = epsilon_override if epsilon_override is not None else self.config.rigidity_epsilon
        self.runtime_config.mode = mode
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

        timestamp = datetime.utcnow().isoformat()
        invariant_hash = sha256_hex(canonical_json(final_output))
        graph_hash = sha256_hex(canonical_json(self.graph.nodes))

        metadata = {
            "timestamp": timestamp,
            "d_s": D_s,
            "d_f": D_f,
            "audit_mode": self.config.audit_mode,
            "mode": mode,
            "epsilon_used": epsilon_used,
            "epsilon": epsilon_used,
            "delta_fp": self.config.delta_fp,
            "correction_flag": correction_flag,
            "admission_metrics": admission_metrics,
            "audit_metrics": extra_metrics,
            "admission_breach": None,
            "service_instance_name": self.config.service_instance_name,
            "invariant_state_hash": invariant_hash,
            "property_graph_hash": graph_hash,
        }

        canonical_state = CanonicalStateDTO(
            data=final_output,
            metadata=metadata,
            source_axioms=all_axioms,
        )

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
            delta_fp=self.config.delta_fp,
            correction_flag=correction_flag,
            source=self.config.service_instance_name,
            metadata=canonical_state.metadata,
        )

        return {
            "canonical_state": canonical_state,
            "output": final_output,
            "kernel_result": kernel_result,
            "audit_receipt": receipt,
            "context_chunks": context_chunks,
        }
