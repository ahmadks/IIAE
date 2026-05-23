"""
Configuración del auditor IDICOC.

Contiene la configuración global del flujo de auditoría y los parámetros
específicos de cada modo de disonancia.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class AuditConfig:
    """Configuración completa del auditor IDICOC."""

    audit_mode: Literal["semantic", "mathematical"] = "semantic"

    rigidity_epsilon: float = 0.0
    delta_fp: float = 0.15
    constant_k: Any = "k"

    enable_hard_halt: bool = False
    service_instance_name: str = "ai_comercial"

    semantic_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_nli_model: str = "facebook/bart-large-mnli"
    semantic_max_rag_results: int = 5
    semantic_min_rag_score: float = 0.1

    mathematical_weights: tuple[float, ...] = (0.15, 0.15, 0.15, 0.15, 0.14, 0.13, 0.13)
    mathematical_delta_fp: float = 0.15
    mathematical_embedding_model: str | None = None

    validate_context_against_axioms: bool = False

    input_field_source: str = "source_input"
    input_field_context: str = "context_input"
    input_field_axioms: str = "context_axioms"

    extra_metadata: dict[str, Any] = field(default_factory=dict)
