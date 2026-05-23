"""
Configuración del wrapper IDICOC.

Todo lo que se configure en el wrapper debe ir en este fichero.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WrapperConfig:
    """Configuración mínima del wrapper IDICOC."""

    constant_k: Any = "k"
    mode: str = "hybrid"
    epsilon_threshold: float = 0.35
    max_rag_results: int = 5
    min_rag_score: float = 0.1
    hallucination_threshold: float = 0.5
    enable_hard_halt: bool = True
    commercial_ai_name: str = "ai_comercial"
    allowed_sources: list[str] = field(default_factory=list)
    extra_metadata: dict[str, Any] = field(default_factory=dict)
