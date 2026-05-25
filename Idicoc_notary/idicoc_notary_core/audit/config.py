"""
Configuración del auditor IDICOC.

Contiene la configuración global del flujo de auditoría y los parámetros
específicos de cada modo de disonancia.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .dse import DissonanceStrategy


@dataclass
class AuditConfig:
    """Configuración completa del auditor IDICOC."""

    # Tolerancias y umbrales configurables.
    # NOTA: Los valores por defecto indicados a continuación son únicamente de referencia
    # y deben ajustarse según las características del dominio específico (banca, IoT, salud, etc.).

    # isg_delta_fp: usado exclusivamente en InvariantStateGenerator (colapso de estados canónicos)
    isg_delta_fp: float = 0.15
    # correction_base_tolerance: tolerancia base para decisión de corrección en DQE (D_s > correction_base_tolerance + epsilon)
    correction_base_tolerance: float = 0.15
    # context_axiom_conflict_threshold: umbral para detectar conflictos entre contexto y axiomas
    context_axiom_conflict_threshold: float = 0.5
    # contradiction_snapping_threshold: umbral de contradicción para snapping fáctico en modo semántico
    contradiction_snapping_threshold: float = 0.5

    rigidity_epsilon: float = 0.0
    """
    Controla el tamaño del manifold admisible (creatividad).
    - Valores cercanos a 0 (ej. 0.0): modo factual, solo respuestas muy cercanas al invariante.
    - Valores intermedios (ej. 0.35): modo híbrido, permite cierta desviación.
    - Valores altos (ej. 0.7): modo creativo, gran libertad (pero sin violar axiomas duros).
    El usuario debe ajustar este valor según la sesión; el notario no lo modifica.
    """
    constant_k: Any = "k"

    # source_name: identificador de la instancia de servicio (antes: service_instance_name)
    source_name: str = "ai_comercial"

    # Paths de persistencia inyectables para AEM / CTM.
    aem_storage_path: str = "tests/results/aem_entropy.json"
    ctm_nodes_path: str = "tests/results/ctm_nodes.json"
    ctm_root_path: str = "ctm_root.txt"
    hardware_key_env_var: str = "IIAE_HARDWARE_KEY"
    require_hardware_seal: bool = False

    # Estrategia de disonancia inyectable.
    # Debe ser una clase que implemente la interfaz DissonanceStrategy.
    # Por defecto utiliza SemanticDissonanceStrategy.
    dissonance_strategy: Any = None

    # Parámetros específicos del modo semántico
    semantic_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_nli_model: str = "facebook/bart-large-mnli"
    semantic_nli_conflict_threshold: float = 0.5
    semantic_nli_warning_threshold: float = 0.75
    semantic_nli_warning_geom_threshold: float = 0.1
    semantic_nli_label_mapping: dict[str, str] = field(default_factory=lambda: {
        "contradiction": "contradiction",
        "entailment": "entailment",
        "neutral": "neutral",
    })
    semantic_embedding_model_signature: str | None = None
    semantic_embedding_model_signature_algo: str = "sha256"
    semantic_max_rag_results: int = 5
    semantic_min_rag_score: float = 0.1
    embedding_normalize: bool = True
    terminal_rigidity_threshold: float = 0.01

    # Configuración de validación y notario
    validate_context_against_axioms: bool = False

    ctm_mode: str = "full"

    # Nota: El parámetro 'mode' (factual/hybrid/creative) ha sido eliminado.
    # La creatividad se controla exclusivamente mediante rigidity_epsilon.

    # El wrapper notario nunca debe bloquear, pero mantenemos el parámetro por compatibilidad.
    enable_hard_halt: bool = False

    # Trazabilidad externa opcional para auditorías y reportes.
    client_id: str | None = None
    trace_input: str | None = None

    # Mapeo configurable de campos de entrada
    input_field_audit: str = "audit_input"
    input_field_context: str = "context_input"
    input_field_axioms: str = "context_axioms"

    extra_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """
        Validaciones y normalizaciones post-inicialización.
        """
        # Si no se proporciona estrategia, usar SemanticDissonanceStrategy por defecto
        if self.dissonance_strategy is None:
            from .dse import SemanticDissonanceStrategy
            self.dissonance_strategy = SemanticDissonanceStrategy

        if self.enable_hard_halt:
            import warnings

            warnings.warn(
                "La opción enable_hard_halt ha sido forzada a False ya que "
                "el wrapper notario opera en modo pasivo y no debe bloquear el flujo.",
                UserWarning,
            )
            self.enable_hard_halt = False
