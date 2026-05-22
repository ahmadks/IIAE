import warnings
import time
import json
import threading
from typing import Any, Dict, Optional, Protocol

from .core.dse import DynamicSchemaExtractor, PropertyGraph
from .core.isg import CanonicalState, InvariantStateGenerator
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
        from .dqe import classify_ds
        self._threshold = threshold
        self._classify_ds = classify_ds

    def _text_similarity(self, candidate: str, canonical: str) -> float:
        candidate_tokens = set(candidate.lower().replace(".", "").replace(",", "").split())
        canonical_tokens = set(canonical.lower().replace(".", "").replace(",", "").split())
        if not canonical_tokens:
            return 0.0
        matched = candidate_tokens.intersection(canonical_tokens)
        return len(matched) / len(canonical_tokens)

    def _project_to_manifold(self, candidate_state: str, canonical_state: CanonicalState) -> str:
        if not candidate_state or not canonical_state.data:
            return canonical_state.data
        # Naive snapping: prefer canonical invariant representation when the candidate is out of bounds.
        return canonical_state.data

    def compute_ds(self, candidate_state: str, canonical_state: CanonicalState, epsilon: float) -> tuple[float, str, str]:
        similarity = self._text_similarity(candidate_state, canonical_state.data)
        ds = 1.0 - similarity
        ds = min(1.0, max(0.0, ds))
        base_type = self._classify_ds(ds)
        corrected = candidate_state if ds <= epsilon else self._project_to_manifold(candidate_state, canonical_state)
        return ds, base_type, corrected

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
        self.config = config or IIAEConfig(**kwargs)
        self._storage = storage or InMemoryStorage()
        self._mao_auditor = mao_auditor

        if self.config.dqe_engine_name == "lexical":
            self.dqe_engine: IDQEEngine = LexicalDQEEngine(threshold=self.config.epsilon_current)
        else:
            raise NotImplementedError("Custom DQE engines not implemented yet")

        self.mao_engine: IMAOEngine = get_engine(
            self.config.mao_engine_name,
            **self.config.mao_engine_params,
        )

        self.isg = InvariantStateGenerator()
        self.dse = DynamicSchemaExtractor()
        self.state_model = StateTransitionModel(
            model_id=self.config.model_id, ctm_salt=self.config.ctm_salt
        )
        self._circuit_trips = self._storage.get_counter()

    def _segregate_entropy(self, candidate_state: str) -> Dict[str, Any]:
        tokens = [t.strip() for t in candidate_state.split() if t.strip()]
        unique_tokens = set(tokens)
        entropy_signature = {
            "eta_t": max(0, len(tokens) - len(unique_tokens)),
            "token_count": len(tokens),
            "unique_token_count": len(unique_tokens),
        }
        return {
            "segregated_state": " ".join(tokens),
            "entropy_map": entropy_signature,
        }

    def _update_epsilon(self, ds: float) -> None:
        alpha = self.config.epsilon_update_alpha
        self.config.epsilon_current = min(
            1.0,
            max(
                0.0,
                (1.0 - alpha) * self.config.epsilon_current + alpha * ds,
            ),
        )

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

        # 1. AEM: segregate non-structural entropy from the candidate state.
        entropy = self._segregate_entropy(response)
        cleaned_response = entropy["segregated_state"]

        # 2. ISG: generate the canonical invariant state C.
        canonical_state = self.isg.generate(rag_context)

        # 3. DSE: extract axioms and build the property graph G_t.
        property_graph = self.dse.extract(rag_context, min_len=self.config.min_len)

        # 4. MAO: evaluate manifold membership before distance calculation when enabled.
        mao_report: MAOReport = {}
        if self.config.enable_mao_filters:
            mao_result = self.mao_engine.evaluate_boundaries(cleaned_response, property_graph)
            mao_report = mao_result or {}
            if mao_report is not None and not mao_report.get("passed", False):
                raise IntegrityError(
                    f"Manifold Boundary Violation: {mao_report.get('reason', 'unspecified')}"
                )

        # 5. DQE: compute distance from the canonical state and project if needed.
        epsilon = self.config.epsilon_current
        ds, base_type, corrected_response = self.dqe_engine.compute_ds(
            cleaned_response, canonical_state, epsilon
        )

        receipt = self.state_model.seal(
            prompt=prompt,
            original_response=response,
            ds=ds,
            axioms=property_graph.axioms,
            canonical_state=canonical_state,
            corrected_response=corrected_response,
            epsilon=epsilon,
            lambda_weights=self.config.lambda_weights,
        )

        duration_ms = (time.time() * 1000) - start_time
        if duration_ms > self.config.timeout_ms:
            logger.error(
                "DQE_TIMEOUT", extra={"iiae_data": {"duration": duration_ms}}
            )
            raise IntegrityError(
                f"Evaluation exceeded timeout of {self.config.timeout_ms}ms"
            )

        log_data = {
            "model_id": self.config.model_id,
            "timeout_ms": self.config.timeout_ms,
            "strict_mode": self.config.strict_mode,
            "enable_mao_filters": self.config.enable_mao_filters,
            "ds": ds,
            "base_type": base_type,
            "axioms_count": len(property_graph.axioms),
            "epsilon": epsilon,
            "ctm_seal": receipt.get("ctm_seal"),
            "corrected_response": corrected_response,
        }

        if self.config.enable_mao_filters:
            log_data["mao"] = mao_report
            if getattr(self, "_mao_auditor", None):
                try:
                    audit_caus = self._mao_auditor.audit_material_causality(response, rag_context)
                    audit_prob = self._mao_auditor.audit_probability_entropy(
                        response, rag_context, property_graph.axioms
                    )
                    audit_axi = self._mao_auditor.audit_axiomatic_invariance(
                        property_graph.axioms, response
                    )
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

        if ds > epsilon:
            self._circuit_trips = self._storage.get_counter() + 1
            self._storage.set_counter(self._circuit_trips)
            if self.config.strict_mode and self._circuit_trips > self.config.max_trips:
                now = time.time() * 1000
                self.config._set_circuit_state(True, now)
                self._storage.set_timestamp(now)
            logger.warning("INTEGRITY_VIOLATION", extra={"iiae_data": log_data})
            self._update_epsilon(ds)
            raise IntegrityError(
                f"Ds={ds} exceeds epsilon={epsilon}. Seal={receipt['ctm_seal']}"
            )

        self._circuit_trips = 0
        self._storage.set_counter(0)
        if self.config._circuit_half_open:
            self.config._reset_circuit()
            self.config._circuit_half_open = False

        self._update_epsilon(ds)
        logger.info("INTEGRITY_VERIFIED", extra={"iiae_data": log_data})

        return EpistemicState(
            ds,
            base_type,
            property_graph.axioms,
            receipt,
            mao=mao_report,
        )

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
