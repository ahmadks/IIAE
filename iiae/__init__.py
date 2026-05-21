from datetime import datetime, timezone
from .config import IIAEConfig
from .supervisor import IIAESupervisor, IntegrityError, CircuitBreakerError
from .epistemic import EpistemicState
from .ctm import verify_receipt
from .state import StateTransitionModel
from .logger import get_logger

SDK_VERSION = "1.0.0"
__version__ = SDK_VERSION
# expose registration API at package level
from .mao.registry import register_engine as register_mao_engine, list_registered_engines
# expose DQE contract for custom engines
from .dqe_contract import IDQEEngine
logger = get_logger("IIAE.Audit")

from .mao.auditor import compare_reports, MAOAuditor

__all__ = [
    "IDQEEngine",
    "register_mao_engine",
    "list_registered_engines",
    "compare_reports",
    "MAOAuditor",
    "validate",
    "manifest",
    "audit",
    "build_manifest",
    "build_audit_record",
    "log_audit_record",
    "verify_audit_chain",
]


def validate(prompt: str, response: str, context: str, config: IIAEConfig | None = None, **kwargs) -> dict:
    """High‑level transaction verification.
    If `config` is omitted, the provided `**kwargs` are used to construct an
    `IIAEConfig` instance (e.g. `IIAEConfig(max_trips=10, ds_threshold=0.5)`).
    """
    cfg = config or IIAEConfig(**kwargs)
    # duplicate cfg assignment removed
    supervisor = IIAESupervisor(config=cfg)
    
    try:
        state = supervisor.verify(prompt, response, context)
        return {
            "verified": True,
            "ds": state.ds,
            "base_type": state.base_type,
            "ctm_seal": state.receipt.get("ctm_seal"),
            "mao": state.mao,
            "receipt": state.receipt
        }
    except IntegrityError as ie:
        return {
            "verified": False,
            "error": "INTEGRITY_VIOLATION",
            "message": str(ie)
        }
    except CircuitBreakerError as cbe:
        return {
            "verified": False,
            "error": "CIRCUIT_BREAKER_HALT",
            "message": str(cbe)
        }

def _manifest_prompt(prompt: str, response: str, context: str, model_id: str = "llm-v1") -> dict:
    """Generate a CTM receipt from prompt/response/context.
    This is the original implementation, now private.
    """
    from .invariant import InvariantEngine
    engine = InvariantEngine()
    axioms = engine.from_context(context)

    from .integrity import IntegrityEvaluator
    evaluator = IntegrityEvaluator()
    ds, _ = evaluator.evaluate(response, axioms)

    model = StateTransitionModel(model_id=model_id)
    return model.seal(prompt, response, ds, axioms)

def manifest(*args, prompt: str = None, response: str = None, context: str = None, model_id: str = "llm-v1", state: EpistemicState = None, extra: dict = None) -> dict:
    """Unified manifest entry point.
    Supports both positional arguments (prompt, response, context) and keyword arguments.
    - If `state` (EpistemicState) is provided, reuse its data via `build_manifest`.
    - If positional args are supplied, they map to `prompt`, `response`, `context` respectively.
    - Otherwise, fall back to the original prompt/response/context workflow.
    """
    # Positional args handling (allow up to 3 positional arguments)
    if len(args) > 3:
        raise TypeError("manifest() takes at most 3 positional arguments (prompt, response, context)")
    if len(args) >= 1:
        prompt = args[0]
    if len(args) >= 2:
        response = args[1]
    if len(args) == 3:
        context = args[2]

    if isinstance(state, EpistemicState):
        return build_manifest(state, extra)
    # Ensure required args for the original flow
    if prompt is None or response is None or context is None:
        raise ValueError("prompt, response, and context must be provided when state is not given")
    receipt = _manifest_prompt(prompt, response, context, model_id)
    # Return receipt directly for compatibility (mirrors original return type)
    return receipt


def audit(receipt: dict | None = None, state: EpistemicState | None = None) -> bool:
    """Forensically validates a sealed receipt block against tampering.
    Accepts either a receipt dict directly or an EpistemicState.
    """
    if isinstance(state, EpistemicState):
        receipt = state.receipt
    if receipt is None:
        raise ValueError("Either 'receipt' or 'state' must be provided to audit().")
    model = StateTransitionModel()
    return model.verify(receipt)

def build_manifest(state: EpistemicState, extra: dict = None) -> dict:
    """
    Constructs a compact manifest for platform integration.
    """
    manifest_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sdk_version": SDK_VERSION,
        "ds": state.ds,
        "base_type": state.base_type,
        "axioms_count": len(state.axioms),
        "ctm": {
            "seal": state.receipt.get("ctm_seal"),
            "model_id": state.receipt.get("payload", {}).get("model_id"),
            "version": state.receipt.get("payload", {}).get("version"),
        },
        "mao": state.mao,
        "is_standard_zero": state.is_standard_zero,
    }
    if extra:
        manifest_data["extra"] = extra
    return manifest_data

def build_audit_record(state: EpistemicState, source: str = "runtime", meta: dict = None) -> dict:
    """
    Constructs a structured audit record.
    """
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "ds": state.ds,
        "base_type": state.base_type,
        "axioms_count": len(state.axioms),
        "ctm": state.receipt,
        "mao": state.mao,
        "meta": meta or {},
    }

def log_audit_record(record: dict) -> None:
    """
    Sends the audit record to the SDK JSON logger.
    """
    logger.info("IIAE_AUDIT_RECORD", extra={"iiae_data": record})

def verify_audit_chain(state: EpistemicState) -> bool:
    """
    Verifies that the CTM associated with the state is integral.
    """
    return verify_receipt(state.receipt)
