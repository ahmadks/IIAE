# idicoc_core/core/pipeline/kernel.py
from __future__ import annotations
from typing import Any
from datetime import datetime
from idicoc_core.util.hashing import sha256_hex

from idicoc_core.exceptions.integrity_breach import HardHaltException, InvariantStateBreach
from idicoc_core.exceptions.alignment_breach import AlignmentBreach


class CustodialKernel:
    """
    CustodialKernel — Motor coálgebraico del sistema.
    Mantiene el estado S y ejecuta la transición ξ: S → F(S).
    """

    def __init__(
        self,
        aem,
        isg,
        verifier,
        ctm,
        dse,
        cmc,
        dqe,
        epsilon: float = 0.0,
    ):
        self.aem = aem
        self.isg = isg
        self.verifier = verifier
        self.ctm = ctm
        self.dse = dse
        self.cmc = cmc
        self.dqe = dqe
        self.epsilon = epsilon

        # Estado coálgebraico S
        self.state_s = {
            "buffers": [None] * 7,
            "registers": [None] * 7
        }

    def process(self, raw_input: Any) -> None:
        # El Kernel fija el tiempo lógico de la operación
        operation_time = datetime.utcnow().isoformat()

        try:
            # Stage 1 — Admission
            admitted = self.aem.admit(raw_input)
            self.state_s["buffers"][0] = admitted

            # Stage 2 — Projection
            canonical_state = self.isg.generate(admitted)
            self.state_s["buffers"][1] = canonical_state

            # Stage 3 — Schema extraction / graph update
            updated_graph = self.dse.update_graph(admitted, canonical_state)
            self.state_s["buffers"][2] = updated_graph

            # Stage 4 — Manifold construction
            manifold = self.cmc.build(canonical_state, updated_graph, self.epsilon)
            self.state_s["buffers"][3] = manifold

            # Stage 5 — Deviation quantification
            dissonance = self.dqe.compute_dissonance(admitted, canonical_state, updated_graph)
            self.state_s["buffers"][4] = dissonance

            if dissonance > self.epsilon:
                corrected_state = self.dqe.project_to_manifold(
                    admitted,
                    manifold,
                    canonical_state,
                    updated_graph,
                )
            else:
                corrected_state = admitted
            self.state_s["buffers"][5] = corrected_state

            # Stage 6 — Verification
            self.verifier.verify_alignment(canonical_state, tolerance=self.epsilon)
            self.state_s["buffers"][6] = "VERIFIED"

            # Stage 7 — Custody (determinista) con metadatos del Anexo K
            invariant_state_hash = sha256_hex(repr(canonical_state.data) + canonical_state.metadata.get("timestamp", ""))
            property_graph_hash = sha256_hex(repr(updated_graph.nodes) + str(updated_graph.edges))
            
            self.ctm.commit(
                corrected_state,
                dissonance=dissonance,
                epsilon=self.epsilon,
                property_graph=updated_graph,
                timestamp=operation_time,
                invariant_state_hash=invariant_state_hash,
                property_graph_hash=property_graph_hash,
            )
            self.state_s["registers"][0] = "COMMITTED"

        except (InvariantStateBreach, AlignmentBreach) as breach:
            snapshot = {
                "kernel_state": self.state_s,
                "breach": breach.serialize_forensic_data()
            }

            # Sellado en el CTM con el mismo tiempo lógico
            self.ctm.seal_failure(snapshot, timestamp=operation_time)

            # Hard Halt
            self._halt()

    def _halt(self) -> None:
        raise HardHaltException()
