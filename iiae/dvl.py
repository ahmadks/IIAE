from .invariant import InvariantEngine
from .integrity import IntegrityEvaluator
from .state import StateTransitionModel
from .epistemic import EpistemicState
from .config import IIAEConfig
from .logger import get_logger
import time

class IntegrityError(Exception):
    pass

class CircuitBreakerError(Exception):
    pass

logger = get_logger("IIAE.Supervisor")

class IIAESupervisor:
    def __init__(self, config: IIAEConfig = None, **kwargs):
        self.config = config or IIAEConfig(**kwargs)
        self.invariant_engine = InvariantEngine(min_len=self.config.min_len)
        self.integrity = IntegrityEvaluator(threshold=self.config.ds_threshold)
        self.state_model = StateTransitionModel(model_id=self.config.model_id)
        
        self.circuit_breaker_trips = 0
        self.circuit_open = False

    def _sanitize(self, text: str) -> str:
        # Basic protection against injection or malformed inputs
        if not text:
            return ""
        return text.replace("\x00", "")

    def verify(self, prompt: str, response: str, rag_context: str) -> EpistemicState:
        if self.circuit_open:
            raise CircuitBreakerError("Circuit Breaker is OPEN. Halting evaluation.")

        start_time = time.time() * 1000
        
        prompt = self._sanitize(prompt)
        response = self._sanitize(response)
        rag_context = self._sanitize(rag_context)

        axioms = self.invariant_engine.from_context(rag_context)
        ds, base_type = self.integrity.evaluate(response, axioms)
        receipt = self.state_model.seal(prompt, response, ds, axioms)

        duration_ms = (time.time() * 1000) - start_time
        
        # Enterprise Timeout Check
        if duration_ms > self.config.timeout_ms:
            logger.error("DQE_TIMEOUT", extra={"iiae_data": {"duration": duration_ms}})
            raise IntegrityError(f"Evaluation exceeded timeout of {self.config.timeout_ms}ms")

        # Logging
        log_data = {
            "ds": ds,
            "base_type": base_type,
            "axioms_count": len(axioms),
            "ctm_seal": receipt.get("ctm_seal")
        }
        
        mao_report = {}
        if self.config.enable_mao_filters:
            from .mao import material_causality_filter, axiomatic_invariance_filter, probability_filter
            mao_report = {
                "material_causality": material_causality_filter(response, rag_context),
                "axiomatic_invariance": axiomatic_invariance_filter(axioms, response),
                "probability_filter": probability_filter(response)
            }
            log_data["mao"] = mao_report
        
        if ds >= self.config.ds_threshold:
            self.circuit_breaker_trips += 1
            if self.config.strict_mode and self.circuit_breaker_trips > 5:
                self.circuit_open = True
            
            logger.warning("INTEGRITY_VIOLATION", extra={"iiae_data": log_data})
            raise IntegrityError(f"Ds={ds} exceeds threshold. Seal={receipt['ctm_seal']}")
        else:
            self.circuit_breaker_trips = 0
            logger.info("INTEGRITY_VERIFIED", extra={"iiae_data": log_data})

        return EpistemicState(ds, base_type, axioms, receipt, mao=mao_report)
