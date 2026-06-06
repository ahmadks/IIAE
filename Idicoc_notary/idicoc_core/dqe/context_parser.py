from __future__ import annotations
from typing import Any, Dict, Optional
from idicoc_core.api.schemas import SessionContext

class ContextParser:
    """
    dqe/context_parser.py
    Dynamic Query Evaluator - Handles formatting and packaging of prompts and RAG contexts.
    """

    def __init__(self, config: Any = None):
        self.config = config

    def build_context(
        self, user_prompt: str, rag_context: str, metadata: Optional[Dict[str, Any]] = None
    ) -> SessionContext:
        """
        Builds a structured SessionContext DTO from raw prompt and context strings.
        """
        return SessionContext(
            user_prompt=user_prompt or "",
            rag_context=rag_context or "",
            metadata=metadata or {}
        )
