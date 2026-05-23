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

    # Tolerancias y umbrales configurables.
    # NOTA: Los valores por defecto indicados a continuación son únicamente de referencia
    # y deben ajustarse según las características del dominio específico (banca, IoT, salud, etc.).
    
    # isg_delta_fp: usado exclusivamente en InvariantStateGenerator (colapso de estados canónicos)
    isg_delta_fp: float = 0.15
    # correction_base_tolerance: tolerancia base para decisión de corrección en DQE (D_s > correction_base_tolerance + epsilon)
    correction_base_tolerance: float = 0.15
    # context_axiom_conflict_threshold: umbral para detectar conflictos entre contexto y axiomas
    context_axiom_conflict_threshold: float = 0.5
    # semantic_contradiction_snapping_threshold: umbral de contradicción para snapping fáctico en modo semántico
    semantic_contradiction_snapping_threshold: float = 0.5

    rigidity_epsilon: float = 0.0
    constant_k: Any = "k"

    # source_name: identificador de la instancia de servicio (antes: service_instance_name)
    source_name: str = "ai_comercial"

    # Parámetros específicos del modo semántico
    semantic_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_nli_model: str = "facebook/bart-large-mnli"
    semantic_max_rag_results: int = 5
    semantic_min_rag_score: float = 0.1

    # Parámetros específicos del modo matemático
    mathematical_weights: tuple[float, ...] = (0.15, 0.15, 0.15, 0.15, 0.14, 0.13, 0.13)
    mathematical_embedding_model: str | None = None

    # Configuración de validación y notario
    validate_context_against_axioms: bool = False

    # Modo de operación del kernel (factual, hybrid, creative)
    mode: Literal["factual", "hybrid", "creative"] = "factual"

    # El wrapper notario nunca debe bloquear, pero mantenemos el parámetro por compatibilidad.
    enable_hard_halt: bool = False

    # Mapeo configurable de campos de entrada
    input_field_source: str = "source_input"
    input_field_context: str = "context_input"
    input_field_axioms: str = "context_axioms"

    extra_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """
        Validaciones y normalizaciones post-inicialización.
        """
        if self.enable_hard_halt:
            import warnings
            warnings.warn(
                "La opción enable_hard_halt ha sido forzada a False ya que "
                "el wrapper notario opera en modo pasivo y no debe bloquear el flujo.",
                UserWarning
            )
            self.enable_hard_halt = False

