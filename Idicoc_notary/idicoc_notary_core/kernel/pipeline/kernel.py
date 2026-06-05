# idicoc_notary_core/kernel/pipeline/kernel.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Protocol, Tuple
from datetime import datetime, timezone
from idicoc_notary_core.utils.hashing import sha256_hex
from idicoc_notary_core.utils.logger import get_logger

from idicoc_notary_core.kernel.exceptions.integrity_breach import (
    HardHaltException,
    InvariantStateBreach,
)
from idicoc_notary_core.kernel.exceptions.alignment_breach import AlignmentBreach

logger = get_logger("kernel.custodial")


class CanonicalState(Protocol):
    @property
    def metadata(self) -> Dict[str, Any]: ...
    @property
    def measure_vector(self) -> Any: ...


class DissonanceEngine(Protocol):
    property_graph: Any | None = None
    def compute_dissonance(self, y: Any, V_hat: Any, G_t: Any) -> float: ...


class AuditEntropyModule(Protocol):
    def get_counters(self) -> Tuple[int, int, int]: ...


class CustodialTraceManager(Protocol):
    @property
    def root_hash(self) -> Optional[str]: ...
    def commit(self, *args, **kwargs) -> Any: ...
    def seal_failure(self, *args, **kwargs) -> Any: ...


class CustodialKernel:
    """
    CustodialKernel — Motor coálgebraico del sistema.
    Mantiene el estado S y ejecuta la transición ξ: S → F(S).
    """

    def __init__(
        self,
        aem: AuditEntropyModule | None,
        isg: Any,
        verifier: Any,
        ctm: CustodialTraceManager,
        dse: DissonanceEngine | None,
        cmc: Any,
        dqe: DissonanceEngine | None = None,
        dissonance_strategy: DissonanceEngine | None = None,
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
        self._epsilon = epsilon
        self.enable_hard_halt = enable_hard_halt
        self._dissonance_history: list[float] = []

        # Estado coálgebraico S
        self.state_s: dict[str, list[Any]] = {"buffers": [None] * 7, "registers": [None] * 7}

    @property
    def epsilon(self) -> float:
        return self._epsilon

    @epsilon.setter
    def epsilon(self, value: float) -> None:
        if hasattr(self, "_epsilon") and value != self._epsilon:
            raise RuntimeError("Parameter mutation violates the Rigidity Theorem.")
        self._epsilon = value

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
        try:
            is_hw = bool(admitted_input.hardware_contained)
        except AttributeError:
            is_hw = False

        if is_hw or self._is_hardware_contained(
            admitted_input, canonical_state_obj, updated_graph
        ):
            logger.info("[Kernel] Señal contenida por MUX. Evaluando métrica de comportamiento...")

            # 2. Cálculo de Ds (Prueba de Equivalencia de Trazas)
            dissonance_engine = None
            try:
                if self.dse is not None:
                    _ = self.dse.compute_dissonance
                    dissonance_engine = self.dse
            except AttributeError:
                pass

            if dissonance_engine is None:
                try:
                    if self.dissonance_strategy is not None:
                        _ = self.dissonance_strategy.compute_dissonance
                        dissonance_engine = self.dissonance_strategy
                except AttributeError:
                    pass

            if dissonance_engine is None:
                try:
                    if self.dqe is not None:
                        _ = self.dqe.compute_dissonance
                        dissonance_engine = self.dqe
                except AttributeError:
                    pass

            if dissonance_engine is not None:
                import inspect
                sig = inspect.signature(dissonance_engine.compute_dissonance)
                if len(sig.parameters) >= 3:
                    ds_metric = dissonance_engine.compute_dissonance(admitted_input, canonical_state_obj, updated_graph)
                else:
                    ds_metric = dissonance_engine.compute_dissonance(admitted_input, updated_graph)
            else:
                ds_metric = 0.0

            try:
                metadata = canonical_state_obj.metadata
                if isinstance(metadata, dict):
                    metadata["dissonance_metrics"] = ds_metric
                    metadata["d_s"] = ds_metric
            except AttributeError:
                pass

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
            if epsilon != self._epsilon:
                raise RuntimeError("Parameter mutation violates the Rigidity Theorem.")
            self.epsilon = epsilon

        # Wrapper backwards compatibility
        from idicoc_notary_core.kernel.projection import CanonicalState
        from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph

        canonical_state_obj = self.isg.generate(canonical_state)
        updated_graph = property_graph
        if updated_graph is None:
            try:
                if self.dse is not None and self.dse.property_graph is not None:
                    updated_graph = self.dse.property_graph
            except AttributeError:
                pass
            if updated_graph is None:
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

        try:
            canonical_payload = self.dissonance_strategy.select_canonical_input(canonical_state_obj)
        except AttributeError:
            try:
                canonical_payload = canonical_state_obj.measure_vector
            except AttributeError:
                canonical_payload = canonical_state_obj

        ts = ""
        try:
            metadata = canonical_state_obj.metadata
            if isinstance(metadata, dict):
                ts = metadata.get("timestamp", "")
        except AttributeError:
            pass
        invariant_state_hash = sha256_hex(repr(canonical_payload) + ts)

        try:
            nodes_repr = updated_graph.nodes
        except AttributeError:
            nodes_repr = []

        try:
            edges_repr = updated_graph.edges
        except AttributeError:
            edges_repr = []
        property_graph_hash = sha256_hex(repr(nodes_repr) + str(edges_repr))

        aem_counters = None
        try:
            if self.aem is not None:
                t_s, v_s, r_s = self.aem.get_counters()
                aem_counters = {
                    "total_signals": t_s,
                    "valid_signals": v_s,
                    "rejected_signals": r_s,
                }
        except AttributeError:
            pass

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
            try:
                return bool(source.hardware_contained)
            except AttributeError:
                pass
            try:
                metadata = source.metadata
                if isinstance(metadata, dict) and metadata.get("hardware_contained"):
                    return True
            except AttributeError:
                pass
            try:
                attr = source.is_hardware_contained
                if callable(attr):
                    try:
                        return bool(attr())
                    except Exception:
                        pass
                else:
                    return bool(attr)
            except AttributeError:
                pass
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
