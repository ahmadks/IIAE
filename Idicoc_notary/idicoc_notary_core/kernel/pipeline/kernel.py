# idicoc_notary_core/kernel/pipeline/kernel.py
from __future__ import annotations
from typing import Any
from datetime import datetime, timezone
from idicoc_notary_core.utils.hashing import sha256_hex

from idicoc_notary_core.kernel.exceptions.integrity_breach import HardHaltException, InvariantStateBreach
from idicoc_notary_core.kernel.exceptions.alignment_breach import AlignmentBreach


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
        dissonance_strategy,
        epsilon: float = 0.0,
        enable_hard_halt: bool = False,
    ):
        self.aem = aem
        self.isg = isg
        self.verifier = verifier
        self.ctm = ctm
        self.dse = dse
        self.cmc = cmc
        self.dqe = dqe
        self.dissonance_strategy = dissonance_strategy
        self.epsilon = epsilon
        self.enable_hard_halt = enable_hard_halt
        self._dissonance_history: list[float] = []

        # Estado coálgebraico S
        self.state_s = {
            "buffers": [None] * 7,
            "registers": [None] * 7
        }

    def process(
        self,
        canonical_state: Any,
        dissonance: float = 0.0,
        epsilon: float = 0.0,
        property_graph: Any = None,
        timestamp: str | None = None,
    ) -> dict[str, Any] | None:
        # Ajustar epsilon según la sesión entrante
        if epsilon is not None:
            self.epsilon = epsilon

        # El Kernel fija el tiempo lógico de la operación
        operation_time = timestamp or datetime.now(timezone.utc).isoformat()

        try:
            # Stage 1 — Admission (notarial, asume estado ya admitido)
            admitted = canonical_state
            self.state_s["buffers"][0] = admitted

            # Stage 2 — Projection
            canonical_state_obj = self.isg.generate(admitted)
            self.state_s["buffers"][1] = canonical_state_obj

            # Stage 3 — Schema extraction / graph update
            updated_graph = self.dse.update_graph(admitted, canonical_state_obj)
            self.state_s["buffers"][2] = updated_graph

            # Stage 4 — Manifold construction
            canonical_input = self.dissonance_strategy.select_canonical_input(canonical_state_obj)
            manifold = self.cmc.build(canonical_input, updated_graph, self.epsilon)
            self.state_s["buffers"][3] = manifold

            # Stage 5 — Deviation quantification
            dissonance = self.dqe.compute_dissonance(admitted, canonical_input, updated_graph)
            self.state_s["buffers"][4] = dissonance
            self._dissonance_history.append(dissonance)

            # Actualizar epsilon dinámicamente
            self.epsilon = self.cmc.update_epsilon(
                current_eps=self.epsilon,
                axiom_density=updated_graph.compute_axiom_density(),
                dissonance_variance=self._compute_recent_variance(),
            )

            if dissonance > self.epsilon:
                corrected_state = self.dqe.project_to_manifold(admitted, manifold, canonical_input, updated_graph)
            else:
                corrected_state = admitted
            self.state_s["buffers"][5] = corrected_state

            # Stage 6 — Verification con tolerancia
            self.verifier.verify_alignment(
                canonical_state_obj,
                tolerance=self.epsilon,
                dqe=self.dqe,
                graph=updated_graph,
            )
            self.state_s["buffers"][6] = "VERIFIED"

            canonical_payload = self.dissonance_strategy.select_canonical_input(canonical_state_obj)
            invariant_state_hash = sha256_hex(repr(canonical_payload) + canonical_state_obj.metadata.get("timestamp", ""))
            property_graph_hash = sha256_hex(repr(updated_graph.nodes) + str(updated_graph.edges))

            aem_counters = None
            if hasattr(self, "aem") and self.aem is not None and hasattr(self.aem, "get_counters"):
                t_s, v_s, r_s = self.aem.get_counters()
                aem_counters = {
                    "total_signals": t_s,
                    "valid_signals": v_s,
                    "rejected_signals": r_s,
                }

            self.ctm.commit(
                canonical_payload,
                dissonance=dissonance,
                epsilon=self.epsilon,
                property_graph=updated_graph,
                timestamp=operation_time,
                invariant_state_hash=invariant_state_hash,
                property_graph_hash=property_graph_hash,
                aem_counters=aem_counters,
            )
            self.state_s["registers"][0] = "COMMITTED"
            return {
                "status": "committed",
                "root_hash": self.ctm.root_hash,
            }

        except (InvariantStateBreach, AlignmentBreach) as breach:
            snapshot = {
                "kernel_state": self.state_s,
                "breach": breach.serialize_forensic_data(),
            }

            self.ctm.seal_failure(snapshot, timestamp=operation_time)
            self.state_s["registers"][0] = "BREACH_RECORDED"
            if self.enable_hard_halt:
                self._halt()
            else:
                self.state_s["registers"][0] = "HALT_SKIPPED"
                return {
                    "status": "breach_recorded",
                    "root_hash": self.ctm.root_hash,
                    "snapshot": snapshot,
                }

        return None

    def _compute_recent_variance(self) -> float:
        if len(self._dissonance_history) < 2:
            return 0.0
        window = self._dissonance_history[-10:]
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        return variance

    def _halt(self) -> None:
        if self.enable_hard_halt:
            raise HardHaltException()
        self.state_s["registers"][0] = "HALT_SKIPPED"
