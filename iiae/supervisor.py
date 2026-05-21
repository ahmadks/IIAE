import warnings
import time
import json
import threading
from typing import Any, Dict, Optional, Protocol

from .invariant import InvariantEngine
from .state import StateTransitionModel
from .epistemic import EpistemicState
from .config import IIAEConfig
from .logger import get_logger

# Contracts / Engine framework
from .dqe_contract import IDQEEngine
from .mao import IMAOEngine, MAOReport, register_engine, get_engine


# Lexical fallback implementations
class LexicalDQEEngine(IDQEEngine):
    def __init__(self, threshold: float):
        # Reuse existing IntegrityEvaluator logic
        from .integrity import IntegrityEvaluator
        self._evaluator = IntegrityEvaluator(threshold=threshold)

    def compute_ds(self, response: str, axioms: list) -> tuple[float, str]:
        ds, base_type = self._evaluator.evaluate(response, axioms)
        return ds, base_type

class IStateStorage(Protocol):
    """Protocol for a simple counter storage used by the circuit‑breaker.

    Implementations must be thread‑safe.
    """

    def get_counter(self) -> int:
        ...

    def set_counter(self, value: int) -> None:
        ...

    def get_timestamp(self) -> Optional[float]:
        ...

    def set_timestamp(self, value: Optional[float]) -> None:
        ...

class InMemoryStorage(IStateStorage):
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counter: int = 0
        self._timestamp: Optional[float] = None

    def get_counter(self) -> int:
        with self._lock:
            return self._counter

    def set_counter(self, value: int) -> None:
        with self._lock:
            self._counter = value

    def get_timestamp(self) -> Optional[float]:
        with self._lock:
            return self._timestamp

    def set_timestamp(self, value: Optional[float]) -> None:
        with self._lock:
            self._timestamp = value


logger = get_logger("IIAE.Supervisor")

class IntegrityError(Exception):
    pass

class CircuitBreakerError(Exception):
    pass

class IIAESupervisor:
    def __init__(self, config: IIAEConfig = None, storage: Optional[IStateStorage] = None, mao_auditor: Any = None, **kwargs: Any):
        # Resolve configuration (fallback to defaults if not provided)
        self.config = config or IIAEConfig(**kwargs)
        # Initialize storage for circuit‑breaker state
        self._storage = storage or InMemoryStorage()
        # Optional auditor for self‑auditing MAO engines
        self._mao_auditor = mao_auditor
        # Initialize DQE engine (lexical fallback by default)
        if self.config.dqe_engine_name == "lexical":
            self.dqe_engine: IDQEEngine = LexicalDQEEngine(threshold=self.config.ds_threshold)
        else:
            raise NotImplementedError("Custom DQE engines not implemented yet")
        # Resolve MAO engine via the registry (default is lexical)
        self.mao_engine: IMAOEngine = get_engine(
            self.config.mao_engine_name,
            **self.config.mao_engine_params,
        )
        # Initialize other components
        self.invariant_engine = InvariantEngine(min_len=self.config.min_len)
        self.state_model = StateTransitionModel(
            model_id=self.config.model_id, ctm_salt=self.config.ctm_salt
        )
        # Circuit‑breaker state uses the injected storage
        self._circuit_trips = self._storage.get_counter()


    def _sanitize(self, text: str) -> str:
        if not text:
            return ""
        return text.replace("\x00", "")

    def verify(self, prompt: str, response: str, rag_context: str) -> EpistemicState:
        # Circuit‑breaker pre‑check with half‑open handling
        if self.config.circuit_open:
            now_ms = time.time() * 1000
            elapsed = now_ms - (self.config.circuit_last_open_ts or 0)
            if elapsed < self.config.cb_cooldown_ms:
                raise CircuitBreakerError("Circuit Breaker is OPEN (cooldown active).")
            # Cooldown elapsed: allow one request in HALF_OPEN state
            self.config._set_circuit_state(False, None)
            self.config._circuit_half_open = True


        start_time = time.time() * 1000
        prompt = self._sanitize(prompt)
        response = self._sanitize(response)
        rag_context = self._sanitize(rag_context)

        axioms = self.invariant_engine.from_context(rag_context)
        ds, base_type = self.dqe_engine.compute_ds(response, axioms)
        receipt = self.state_model.seal(prompt, response, ds, axioms)

        duration_ms = (time.time() * 1000) - start_time
        if duration_ms > self.config.timeout_ms:
            logger.error(
                "DQE_TIMEOUT", extra={"iiae_data": {"duration": duration_ms}}
            )
            raise IntegrityError(
                f"Evaluation exceeded timeout of {self.config.timeout_ms}ms"
            )

        # Logging data
        log_data = {
            "model_id": self.config.model_id,
            "timeout_ms": self.config.timeout_ms,
            "strict_mode": self.config.strict_mode,
            "enable_mao_filters": self.config.enable_mao_filters,
            "ds": ds,
            "base_type": base_type,
            "axioms_count": len(axioms),
            "ctm_seal": receipt.get("ctm_seal"),
        }

        mao_report: MAOReport = {}
        if self.config.enable_mao_filters:
            mao_report = {
                "material_causality": self.mao_engine.material_causality(
                    response, rag_context
                ),
                "probability_entropy": self.mao_engine.probability_entropy(
                    response, rag_context, axioms
                ),
                "axiomatic_invariance": self.mao_engine.axiomatic_invariance(
                    axioms, response
                ),
                "geoclimatic_synchrony": self.mao_engine.geoclimatic_synchrony(
                    response, rag_context
                ),
            }
            log_data["mao"] = mao_report
            # Optional self‑auditing using provided MAOAuditor
            if getattr(self, "_mao_auditor", None):
                try:
                    audit_caus = self._mao_auditor.audit_material_causality(response, rag_context)
                    audit_prob = self._mao_auditor.audit_probability_entropy(
                        response, rag_context, axioms
                    )
                    audit_axi = self._mao_auditor.audit_axiomatic_invariance(axioms, response)
                    audit_geo = self._mao_auditor.audit_geoclimatic_synchrony(
                        response, rag_context
                    )
                    log_data["mao_audit"] = {
                        "material_causality": audit_caus,
                        "probability_entropy": audit_prob,
                        "axiomatic_invariance": audit_axi,
                        "geoclimatic_synchrony": audit_geo,
                    }
                except Exception as exc:  # pragma: no cover – auditor optional
                    logger.warning("MAO auditor failed: %s", exc)

        if ds > self.config.ds_threshold:
            # Increment persistent counter
            self._circuit_trips = self._storage.get_counter() + 1
            self._storage.set_counter(self._circuit_trips)
            if (
                self.config.strict_mode
                and self._circuit_trips > self.config.max_trips
            ):
                # Open circuit and record timestamp
                now = time.time() * 1000
                self.config._set_circuit_state(True, now)
                self._storage.set_timestamp(now)
            logger.warning("INTEGRITY_VIOLATION", extra={"iiae_data": log_data})
            raise IntegrityError(
                f"Ds={ds} exceeds threshold. Seal={receipt['ctm_seal']}"
            )

        else:
            # Reset persistent counter on success
            self._circuit_trips = 0
            self._storage.set_counter(0)
            # If we were in HALF_OPEN, fully close the circuit
            if self.config._circuit_half_open:
                self.config._reset_circuit()
                self.config._circuit_half_open = False
            logger.info("INTEGRITY_VERIFIED", extra={"iiae_data": log_data})


        return EpistemicState(ds, base_type, axioms, receipt, mao=mao_report)

    def validate(self, *args: Any, **kwargs: Any) -> EpistemicState:
        """Legacy public entry point.

        Emits a DeprecationWarning and forwards to :meth:`verify`.
        """
        warnings.warn(
            "`validate` is deprecated; use `verify` instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        return self.verify(*args, **kwargs)
