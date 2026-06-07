from typing import Any, List, Optional, Tuple

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

    def generate(
        self,
        user_prompt: str,
        rag_context: str | List[str],
        context_policies: Optional[List[Any]] = None,
        epsilon_override: Optional[float] = None,
        **kwargs
    ) -> Tuple[str, NotaryAuditResult]:
        """
        Generates output under Generative Containment (PromptProjector)
        and performs post-generation audit on the output.
        """
        return self.pipeline.generate(
            user_prompt=user_prompt,
            rag_context=rag_context,
            context_policies=context_policies,
            epsilon_override=epsilon_override,
            **kwargs
        )

    def get_aem_counters(self) -> dict[str, float]:
        """
        Retorna los contadores de auditoría del AEM:
          - y_total: total de señales procesadas por el DQE
          - y_valid: señales válidas/corregidas
        """
        return {
            "y_total": self.pipeline.aem.y_total,
            "y_valid": self.pipeline.aem.y_valid,
        }

    @property
    def y_total(self) -> float:
        """Total signals processed by DQE (as float)"""
        return self.pipeline.aem.y_total

    @property
    def y_valid(self) -> float:
        """Signals validated/corrected by DQE (as float)"""
        return self.pipeline.aem.y_valid

    # Alias funcional para compatibilidad
    audit = auditar
