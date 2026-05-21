"""
Enterprise Integration Pipeline

Universal RAG → AI → IIAE → CTM → Audit pattern for all enterprises.
"""

from typing import Any, Dict, Optional

# Import from core modules directly to avoid circular imports
from iiae.config import IIAEConfig
from iiae.supervisor import IIAESupervisor
from iiae.core import build_audit_record, log_audit_record
from .interfaces import RAGBackend, LLMBackend


class PipelineResult(dict):
    """
    Canonical enterprise result from the pipeline.

    Attributes:
        status: "approved" | "blocked" | "error"
        response: The AI response (if approved) or None
        error: Error message (if blocked/error)
        ctm: CTM receipt (cryptographic proof)
        raw_state: Optional debug information (if debug=True)
    """

    pass


def run_enterprise_pipeline(
    user_query: str,
    rag: RAGBackend,
    llm: LLMBackend,
    config: Optional[IIAEConfig] = None,
    *,
    source: str = "enterprise_app",
    meta: Optional[Dict[str, Any]] = None,
    debug: bool = False,
) -> PipelineResult:
    """
    Universal enterprise pattern: RAG → AI → IIAE → CTM.

    This is the canonical way for enterprises to integrate IIAE.

    Flow:
    1. Retrieve context from RAG
    2. Generate response from LLM
    3. Verify with IIAE
    4. Generate CTM receipt
    5. Log audit record

    Args:
        user_query: The user's question/prompt
        rag: RAG backend implementation (retrieves context)
        llm: LLM backend implementation (generates response)
        config: IIAEConfig (optional, uses defaults if None)
        source: Source identifier for audit logging
        meta: Additional metadata for audit record
        debug: If True, include raw verification state

    Returns:
        PipelineResult with status, response, and receipt
    """

    cfg = config or IIAEConfig()
    supervisor = IIAESupervisor(config=cfg)

    try:
        # ─────────────────────────────────────────────────────────────────
        # 1. Retrieve context from RAG
        # ─────────────────────────────────────────────────────────────────
        context = rag.retrieve(user_query)

        # ─────────────────────────────────────────────────────────────────
        # 2. Generate response from LLM
        # ─────────────────────────────────────────────────────────────────
        response = llm.generate(prompt=user_query, context=context)

        # ─────────────────────────────────────────────────────────────────
        # 3. Verify with IIAE
        # ─────────────────────────────────────────────────────────────────
        state = supervisor.verify(user_query, response, context)

        # ─────────────────────────────────────────────────────────────────
        # 4. Build audit record
        # ─────────────────────────────────────────────────────────────────
        record = build_audit_record(
            state=state,
            source=source,
            meta=meta or {},
        )

        # ─────────────────────────────────────────────────────────────────
        # 5. Log audit record
        # ─────────────────────────────────────────────────────────────────
        log_audit_record(record, config=cfg)

        # ─────────────────────────────────────────────────────────────────
        # 6. Prepare result
        # ─────────────────────────────────────────────────────────────────
        result: PipelineResult = PipelineResult(
            status="approved",
            response=response,
            error=None,
            ctm=state.receipt,
        )

        if debug:
            result["raw_state"] = state

        return result

    except Exception as e:
        # Error in pipeline (RAG, LLM, or IIAE)
        return PipelineResult(
            status="error",
            response=None,
            error=str(e),
            ctm=None,
        )

