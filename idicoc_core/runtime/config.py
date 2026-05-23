# idicoc_core/runtime/config.py
from __future__ import annotations
from datetime import datetime
from typing import Callable, Optional

from idicoc_core.core.source.anchor import SourceAnchor
from idicoc_core.core.admission.aem import AnomalousEventManager
from idicoc_core.core.projection.invariant_state_generator import InvariantStateGenerator
from idicoc_core.core.verification.verifier import InvariantVerifier
from idicoc_core.core.verification.registry import ProjectionRegistry
from idicoc_core.core.custody.merkle_dag import CustodialTraceManager, MerkleDAG, EnvHardwareSealer
from idicoc_core.core.pipeline.kernel import CustodialKernel
from idicoc_core.core.graph.property_graph import PropertyGraph
from idicoc_core.core.dse.dse import DynamicSchemaExtractor
from idicoc_core.core.manifold.cmc import ManifoldConstructor
from idicoc_core.core.deviation.dqe import DeviationQuantifier

from idicoc_utils.logger import configure_logging


class RuntimeConfig:
    """
    RuntimeConfig — Punto único de ensamblaje del sistema IDICOC‑IIAE.

    Este módulo:
    - Inicializa logging
    - Construye Anchor, AEM, ISG, Verifier, CTM
    - Expone kernel_factory para el Guardian y el ProcessLoop
    """

    def __init__(
        self,
        constant_k,
        entropy_analyzer,
        property_graph: Optional[PropertyGraph] = None,
        mode: str = "factual",
        rigidity_epsilon: float = 0.0,
        delta_fp: float = 0.15,
        enable_hard_halt: bool = False,
        log_destination: str = "stdout",
    ):
        # Logging global
        configure_logging(log_destination)

        self.property_graph = property_graph or PropertyGraph()
        self.mode = mode
        self.epsilon = rigidity_epsilon
        self.delta_fp = delta_fp
        self.enable_hard_halt = enable_hard_halt

        # 1. Anchor (k)
        self.anchor = SourceAnchor(constant_k)

        # 2. AEM
        self.aem = AnomalousEventManager(
            property_graph=self.property_graph,
            analyzer=entropy_analyzer,
            threshold=0.85
        )

        # 3. ISG
        self.registry = ProjectionRegistry()
        self.isg = InvariantStateGenerator(
            anchor=self.anchor,
            registry=self.registry,
            delta_fp=self.delta_fp
        )

        # 4. Verifier
        self.verifier = InvariantVerifier(self.anchor)

        # 5. DSE
        self.dse = DynamicSchemaExtractor(self.property_graph)

        # 6. Deviation quantifier
        self.dqe = DeviationQuantifier(delta_fp=delta_fp)

        # 7. Manifold constructor
        self.cmc = ManifoldConstructor(dqe=self.dqe)

        # 8. CTM
        self.hardware_sealer = EnvHardwareSealer()
        self.ctm = CustodialTraceManager(dag=MerkleDAG(sealer=self.hardware_sealer))

        genesis_metadata = {
            "delta_fp": self.delta_fp,
            "lambda_weights": (
                self.dqe.lambda_inv,
                self.dqe.lambda_logic,
                self.dqe.lambda_temporal,
            ),
            "epsilon_0": self.epsilon,
            "mode": self.mode,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.ctm.initialize_genesis(genesis_metadata, timestamp=genesis_metadata["timestamp"])

    def kernel_factory(self) -> Callable[[], CustodialKernel]:
        """
        Devuelve una función que crea un Kernel fresco.
        El Guardian la usará para reinstanciar el universo tras un Hard Halt.
        """
        def _factory():
            return CustodialKernel(
                aem=self.aem,
                isg=self.isg,
                verifier=self.verifier,
                ctm=self.ctm,
                dse=self.dse,
                cmc=self.cmc,
                dqe=self.dqe,
                mode=self.mode,
                epsilon=self.epsilon,
                enable_hard_halt=self.enable_hard_halt,
            )
        return _factory
