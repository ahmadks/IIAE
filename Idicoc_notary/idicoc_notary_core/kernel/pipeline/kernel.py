# idicoc_notary_core/kernel/pipeline/kernel.py
from __future__ import annotations
from typing import Any
from datetime import datetime, timezone
from idicoc_notary_core.utils.hashing import sha256_hex
from idicoc_notary_core.utils.logger import get_logger

from idicoc_notary_core.kernel.exceptions.integrity_breach import (
    HardHaltException,
    InvariantStateBreach,
)
from idicoc_notary_core.kernel.exceptions.alignment_breach import AlignmentBreach

logger = get_logger("kernel.custodial")


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
        dqe=None,
        dissonance_strategy=None,
        epsilon: float = 0.0,
        enable_hard_halt: bool = False,
    ):
        self.aem = aem
        self.isg = isg
        self.verifier = verifier
        self.ctm = ctm
        self.dse = dse
        self.cmc = cmc
        self._dqe = dqe
        self.dissonance_strategy = dissonance_strategy
        self.epsilon = epsilon
        self.enable_hard_halt = enable_hard_halt
        self._dissonance_history: list[float] = []

        # Estado coálgebraico S
        self.state_s: dict[str, list[Any]] = {"buffers": [None] * 7, "registers": [None] * 7}

    @property
    def dqe(self) -> Any:
        # Fallback redirect to support legacy tests accessing kernel.dqe
        return self._dqe or self.dissonance_strategy

    def execute(
        self,
        admitted_input: Any,
        canonical_state_obj: Any,
        updated_graph: Any,
        timestamp: str | None = None,
    ) -> dict[str, Any] | None:
        operation_time = timestamp or datetime.now(timezone.utc).isoformat()

        # Record logic buffers
        self.state_s["buffers"][0] = admitted_input
        self.state_s["buffers"][1] = canonical_state_obj
        self.state_s["buffers"][2] = updated_graph
        self.state_s["buffers"][5] = admitted_input

        # 1. Bypass por hardware (MUX)
        if getattr(admitted_input, "hardware_contained", False) or self._is_hardware_contained(
            admitted_input, canonical_state_obj, updated_graph
        ):
            logger.info("[Kernel] Señal contenida por MUX. Evaluando métrica de comportamiento...")

            # 2. Cálculo de Ds (Prueba de Equivalencia de Trazas)
            dissonance_engine = None
            if hasattr(self, "dse") and self.dse is not None and hasattr(self.dse, "compute_dissonance"):
                dissonance_engine = self.dse
            elif hasattr(self, "dissonance_strategy") and self.dissonance_strategy is not None and hasattr(self.dissonance_strategy, "compute_dissonance"):
                dissonance_engine = self.dissonance_strategy
            elif hasattr(self, "dqe") and self.dqe is not None and hasattr(self.dqe, "compute_dissonance"):
                dissonance_engine = self.dqe

            if dissonance_engine is not None:
                import inspect
                sig = inspect.signature(dissonance_engine.compute_dissonance)
                if len(sig.parameters) >= 3:
                    ds_metric = dissonance_engine.compute_dissonance(admitted_input, canonical_state_obj, updated_graph)
                else:
                    ds_metric = dissonance_engine.compute_dissonance(admitted_input, updated_graph)
            else:
                ds_metric = 0.0

            if hasattr(canonical_state_obj, "metadata") and isinstance(canonical_state_obj.metadata, dict):
                canonical_state_obj.metadata["dissonance_metrics"] = ds_metric
                canonical_state_obj.metadata["d_s"] = ds_metric

            # 3. Consolidación Inmutable
            return self._finalize_custody(admitted_input, canonical_state_obj, updated_graph, ds_metric, operation_time)

        # Fail-Safe crítico
        raise InvariantStateBreach(
            message="La señal evadió la máscara estructural (no es hardware_contained).",
            invalid_state=admitted_input,
            origin="CustodialKernel.execute",
        )

    def process(
        self,
        canonical_state: Any,
        dissonance: float = 0.0,
        epsilon: float = 0.0,
        property_graph: Any = None,
        timestamp: str | None = None,
    ) -> dict[str, Any] | None:
        if epsilon is not None:
            self.epsilon = epsilon

        # Wrapper backwards compatibility
        from idicoc_notary_core.kernel.projection import CanonicalState
        from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph

        canonical_state_obj = self.isg.generate(canonical_state)
        updated_graph = property_graph
        if updated_graph is None:
            if hasattr(self.dse, "property_graph") and self.dse.property_graph is not None:
                updated_graph = self.dse.property_graph
            else:
                updated_graph = PropertyGraph()

        try:
            return self.execute(
                admitted_input=canonical_state,
                canonical_state_obj=canonical_state_obj,
                updated_graph=updated_graph,
                timestamp=timestamp,
            )
        except (InvariantStateBreach, AlignmentBreach) as breach:
            operation_time = timestamp or datetime.now(timezone.utc).isoformat()
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

    def _finalize_custody(
        self,
        admitted: Any,
        canonical_state_obj: Any,
        updated_graph: Any,
        dissonance: float,
        operation_time: str,
    ) -> dict[str, Any]:
        # Stage 6 — Verification con tolerancia
        self.verifier.verify_alignment(
            canonical_state_obj,
            tolerance=self.epsilon,
            dqe=self.dissonance_strategy or self.dqe,
            graph=updated_graph,
        )
        self.state_s["buffers"][6] = "VERIFIED"

        if hasattr(self.dissonance_strategy, "select_canonical_input"):
            canonical_payload = self.dissonance_strategy.select_canonical_input(canonical_state_obj)
        else:
            canonical_payload = getattr(canonical_state_obj, "measure_vector", canonical_state_obj)

        ts = ""
        if hasattr(canonical_state_obj, "metadata") and isinstance(canonical_state_obj.metadata, dict):
            ts = canonical_state_obj.metadata.get("timestamp", "")
        invariant_state_hash = sha256_hex(repr(canonical_payload) + ts)

        nodes_repr = getattr(updated_graph, "nodes", [])
        edges_repr = getattr(updated_graph, "edges", [])
        property_graph_hash = sha256_hex(repr(nodes_repr) + str(edges_repr))

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

    def _compute_recent_variance(self) -> float:
        if len(self._dissonance_history) < 2:
            return 0.0
        window = self._dissonance_history[-10:]
        mean = sum(window) / len(window)
        variance = sum((x - mean) ** 2 for x in window) / len(window)
        return variance

    def _is_hardware_contained(
        self,
        admitted: Any,
        canonical_state_obj: Any,
        updated_graph: Any,
    ) -> bool:
        """Detecta señales ya contenidas por hardware para evitar proyecciones innecesarias."""

        def _extract_flag(source: Any) -> bool:
            if isinstance(source, dict):
                return bool(source.get("hardware_contained", False))
            if hasattr(source, "hardware_contained"):
                return bool(getattr(source, "hardware_contained"))
            if hasattr(source, "metadata"):
                metadata = getattr(source, "metadata")
                if isinstance(metadata, dict) and metadata.get("hardware_contained"):
                    return True
            if hasattr(source, "is_hardware_contained"):
                attr = getattr(source, "is_hardware_contained")
                if callable(attr):
                    try:
                        return bool(attr())
                    except Exception:
                        pass
                else:
                    return bool(attr)
            return False

        if _extract_flag(admitted):
            return True
        if _extract_flag(canonical_state_obj):
            return True
        if _extract_flag(updated_graph):
            return True
        return False

    def _halt(self) -> None:
        if self.enable_hard_halt:
            raise HardHaltException()
        self.state_s["registers"][0] = "HALT_SKIPPED"



    def _apply_emergency_correction(self, admitted: Any) -> Any:
        raise InvariantStateBreach(
            message="Emergency correction triggered: signal is not hardware-contained.",
            invalid_state=admitted,
            origin="CustodialKernel._apply_emergency_correction",
        )
