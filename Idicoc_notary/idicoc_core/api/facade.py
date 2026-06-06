from __future__ import annotations
from typing import Any, List, Optional

from idicoc_core.api.schemas import NotaryAuditResult
from idicoc_core.pipeline.orchestrator import AuditPipeline
from idicoc_core.config import AuditConfig


class NotaryClient:
    """
    Main client facade for the IDICOC Notary.
    Shields the integrator from complex mathematical and cryptographic details.
    """

    def __init__(self, config: AuditConfig):
        self.config = config
        self.pipeline = AuditPipeline(config)

    def audit(
        self,
        user_prompt: str,
        rag_context: str,
        llm_output: str,
        context_policies: Optional[List[Any]] = None,
        epsilon_override: Optional[float] = None
    ) -> NotaryAuditResult:
        """
        Main entry point for the IDICOC Notary.
        Evaluates the LLM output against the active policies and session context.
        """
        return self.pipeline.execute_audit(
            user_prompt=user_prompt,
            rag_context=rag_context,
            llm_output=llm_output,
            context_policies=context_policies,
            epsilon_override=epsilon_override
        )



