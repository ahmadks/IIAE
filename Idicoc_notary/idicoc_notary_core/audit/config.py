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
    from .graph.loader import AxiomLoader


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

    # instance_name: identificador de la instancia de servicio
    instance_name: str = "ai_comercial"

    # Paths de persistencia inyectables para CTM.
    ctm_nodes_path: str = "Idicoc_notary/tests/results/ctm_nodes.json"
    ctm_root_path: str = "ctm_root.txt"
    hardware_key_env_var: str = "IIAE_HARDWARE_KEY"
    require_hardware_seal: bool = False

    # Configuración de backends de persistencia avanzados para CTM
    ctm_storage_backend: Any = "file"
    ctm_postgres_uri: str | None = None
    ctm_dynamodb_table: str | None = None
    ctm_qldb_ledger: str | None = None
    ctm_storage_kwargs: dict[str, Any] = field(default_factory=dict)

    # Pesos de disonancia para las 7 etapas de la especificación IDICOC-DSE (lambda_0..lambda_6)
    dissonance_weights: tuple[float, float, float, float, float, float, float] = (
        0.0,
        0.5,
        0.4,
        0.1,
        0.0,
        0.0,
        0.0,
    )

    # Estrategia de disonancia inyectable.
    # Debe ser una clase que implemente la interfaz DissonanceStrategy.
    # Por defecto utiliza SemanticDissonanceStrategy.
    dissonance_strategy: Any = None

    # Parámetros específicos de evaluación semántica
    semantic_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_nli_model: str = "facebook/bart-large-mnli"
    semantic_nli_conflict_threshold: float = 0.5
    semantic_nli_warning_threshold: float = 0.75
    semantic_nli_warning_geom_threshold: float = 0.1
    semantic_nli_label_mapping: dict[str, str] = field(
        default_factory=lambda: {
            "contradiction": "contradiction",
            "entailment": "entailment",
            "neutral": "neutral",
        }
    )
    semantic_embedding_model_signature: str | None = None
    semantic_embedding_model_signature_algo: str = "sha256"
    semantic_max_rag_results: int = 5
    semantic_min_rag_score: float = 0.1
    embedding_normalize: bool = True
    embedding_signature: str | None = None
    strict_embedding_signature: bool = False
    terminal_rigidity_threshold: float = 0.01
    embedding_max_chunks: int = 10

    ctm_mode: str = "full"

    # Hiperparámetros dinámicos para optimización SPSA
    spsa_a: float = 0.1
    spsa_c: float = 1e-4
    spsa_alpha: float = 0.602
    spsa_gamma: float = 0.101
    spsa_decay_enabled: bool = True

    # Sistema de inyección de axiomas
    axiom_loader: "AxiomLoader | None" = None
    axiom_file_path: str = "axioms.txt"

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
        import os

        # Asegurar que las rutas de persistencia relativas se resuelvan siempre respecto al directorio raíz del proyecto 'Idicoc_notary'
        package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        # Calcular firma del modelo si no se proporciona
        if not self.embedding_signature:
            from idicoc_notary_core.utils.embedding_utils import compute_embedding_signature

            self.embedding_signature = compute_embedding_signature(
                self.semantic_embedding_model, normalize=self.embedding_normalize
            )

        if not os.path.isabs(self.ctm_nodes_path):
            self.ctm_nodes_path = os.path.abspath(os.path.join(package_root, self.ctm_nodes_path))
        if not os.path.isabs(self.ctm_root_path):
            self.ctm_root_path = os.path.abspath(os.path.join(package_root, self.ctm_root_path))

        if self.axiom_loader is None:
            axiom_path = self.axiom_file_path
            if not os.path.isabs(axiom_path):
                axiom_path = os.path.abspath(os.path.join(package_root, axiom_path))
            if os.path.exists(axiom_path):
                from .graph.loader import FileAxiomLoader

                self.axiom_loader = FileAxiomLoader(axiom_path)

        # Si no se proporciona estrategia, usar StructuralDissonanceStrategy por defecto
        if self.dissonance_strategy is None:
            from .dse import StructuralDissonanceStrategy

            self.dissonance_strategy = StructuralDissonanceStrategy

        if self.enable_hard_halt:
            import warnings

            warnings.warn(
                "La opción enable_hard_halt ha sido forzada a False ya que "
                "el wrapper notario opera en modo pasivo y no debe bloquear el flujo.",
                UserWarning,
            )
            self.enable_hard_halt = False
