from __future__ import annotations
from typing import Any, List, Optional

from idicoc_core.api.schemas import NotaryAuditResult
from idicoc_core.pipeline.orchestrator import AuditPipeline
from idicoc_core.config import AuditConfig


class NotaryClient:
    """
    Fachada Principal IDICOC. Implementa el patrón Blackbox para el Custodial Kernel.
    """

    def __init__(self, config: AuditConfig, llm_provider: Any = None):
        # El proveedor LLM real se inyecta desde la app
        self.pipeline = AuditPipeline(config, llm_provider)
        self.config = config

    def auditar(
        self,
        user_prompt: str,
        rag_context: str,
        llm_output: str,
        context_policies: Optional[List[Any]] = None,
        epsilon_override: Optional[float] = None
    ) -> NotaryAuditResult:
        """
        Proyecta la salida estocástica sobre la Variedad de Invarianza (Manifold).
        """
        return self.pipeline.execute_audit(
            user_prompt=user_prompt,
            rag_context=rag_context,
            llm_output=llm_output,
            context_policies=context_policies,
            epsilon_override=epsilon_override
        )

    # Alias funcional para compatibilidad
    audit = auditar
