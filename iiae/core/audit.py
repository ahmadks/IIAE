"""
Audit logging and record building.

Functions for creating structured audit records and logging them.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .receipts import verify_receipt


def build_audit_record(
    state: Optional[Any] = None,
    source: str = "runtime",
    meta: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Constructs a structured audit record.

    Can be called with either:
    - state: EpistemicState object (preferred)
    - Individual fields via kwargs
    """

    if state is not None and hasattr(state, "__dict__"):
        # From EpistemicState
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "ds": getattr(state, "ds", None),
            "base_type": getattr(state, "base_type", None),
            "axioms_count": len(getattr(state, "axioms", [])),
            "ctm": getattr(state, "receipt", {}),
            "mao": getattr(state, "mao", {}),
            "meta": meta or {},
        }
    else:
        # From kwargs (for dict-like results)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "ds": kwargs.get("ds"),
            "base_type": kwargs.get("base_type"),
            "axioms_count": kwargs.get("axioms_count", 0),
            "ctm": kwargs.get("receipt", {}),
            "mao": kwargs.get("mao", {}),
            "meta": meta or {},
        }


def log_audit_record(record: Dict[str, Any], config: Optional[Any] = None) -> None:
    """
    Send a structured audit record to the configured log destination.

    Destination controlled by IIAEConfig.log_destination or IIAE_LOG_DESTINATION env var.
    """
    if config is not None:
        from iiae.logger import configure_logging

        configure_logging(config.log_destination)

    from iiae.logger import get_logger

    logger = get_logger("IIAE.Audit")
    logger.info("IIAE_AUDIT_RECORD", extra={"iiae_data": record})


def verify_audit_chain(state: Optional[Any]) -> bool:
    """
    Verifies that the CTM associated with the state is integral.
    """
    if state is None:
        return False

    receipt = getattr(state, "receipt", None)
    if receipt is None:
        return False

    return verify_receipt(receipt)
