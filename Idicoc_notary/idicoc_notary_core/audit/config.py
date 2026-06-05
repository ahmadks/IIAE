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
    from .graph.loader import PolicyLoader


@dataclass
class AuditConfig:
    """Configuración completa del auditor IDICOC."""

    # Tolerancias y umbrales configurables.
    # NOTA: Los valores por defecto indicados a continuación son únicamente de referencia
    # y deben ajustarse según las características del dominio específico (banca, IoT, salud, etc.).

    # correction_base_tolerance: tolerancia base para decisión de corrección en DQE (D_s > correction_base_tolerance + epsilon)
    correction_base_tolerance: float = 0.15

    rigidity_epsilon: float = 0.0
    """
    Controla el tamaño del manifold admisible (creatividad).
    - Valores cercanos a 0 (ej. 0.0): modo factual, solo respuestas muy cercanas al invariante.
    - Valores intermedios (ej. 0.35): modo híbrido, permite cierta desviación.
    - Valores altos (ej. 0.7): modo creativo, gran libertad (pero sin violar politicas duros).
    El usuario debe ajustar este valor según la sesión; el notario no lo modifica.
    """
    # instance_name: identificador de la instancia de servicio
    instance_name: str = "ai_comercial"

    # Paths de persistencia inyectables para CTM.
    ctm_nodes_path: str = "Idicoc_notary/tests/results/ctm_nodes.json"
    ctm_root_path: str = "ctm_root.txt"
    ctm_wal_path: str | None = None  # Si es None, se deriva automáticamente de ctm_nodes_path
    hardware_key_env_var: str = "IIAE_HARDWARE_KEY"
    require_hardware_seal: bool = False

    # Configuración de backends de persistencia avanzados para CTM
    ctm_storage_backend: Any = "file"
    ctm_postgres_uri: str | None = None
    ctm_dynamodb_table: str | None = None
    ctm_qldb_ledger: str | None = None
    ctm_storage_kwargs: dict[str, Any] = field(default_factory=dict)

    # Pesos de disonancia para las 7 etapas de la especificación IDICOC-DSE (lambda_0..lambda_6)
    #
    # ETAPAS ACTIVAS (λ > 0):
    #   λ₁ — d₁ (EMD al ancla K):          métrica principal de distancia al invariante.
    #   λ₂ — d₂ (Property Graph / politicas): violación de restricciones simbólicas.
    #   λ₃ — d₃ (bisimulación temporal):    divergencia de trazas históricas.
    #
    # ETAPAS INACTIVAS (λ = 0) — siempre devuelven d_i = 0.0:
    #   λ₀ — d₀ (Levenshtein): solo aplica si el input tiene '.text_content' (string).
    #             En el pipeline numérico/algebraico el campo está vacío → d₀ ≡ 0.
    #   λ₄ — d₄ (Hamming criptográfico): requiere comparación de hashes SHA-256
    #             entre estados de ledger consecutivos; no hay dos hashes disponibles
    #             en el momento de evaluar D_s dentro del mismo ciclo de auditoría.
    #   λ₅ — d₅ (Boundary trap): el estado del trap del CustodialKernel (SEMANTIC_SCOPE_VIOLATION)
    #             es una señal de sistema operativo que no está conectada al pipeline Python.
    #   λ₆ — d₆ (convergencia asintótica): requiere dist(s₆, K) sobre el estado terminal
    #             del pipeline completo, que solo existe tras N iteraciones acumuladas;
    #             no es computable en tiempo real por ciclo de auditoría.
    #
    # Los pesos se normalizan automáticamente en _normalized_weights.
    dissonance_weights: tuple[float, float, float, float, float, float, float] = (
        0.0,  # λ₀ — d₀ Levenshtein        (INACTIVO: input numérico, sin text_content)
        0.5,  # λ₁ — d₁ EMD al ancla K     (ACTIVO)
        0.4,  # λ₂ — d₂ Property Graph     (ACTIVO)
        0.1,  # λ₃ — d₃ bisimulación temp. (ACTIVO)
        0.0,  # λ₄ — d₄ Hamming cripto.    (INACTIVO: hashes no disponibles en ciclo)
        0.0,  # λ₅ — d₅ Boundary trap      (INACTIVO: señal SO, no conectada al pipeline)
        0.0,  # λ₆ — d₆ convergencia asint.(INACTIVO: requiere estado terminal acumulado)
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

    # Sistema de inyección de politicas
    policy_loader: "PolicyLoader | None" = None
    policy_file_path: str = "policies.txt"

    # Proveedor de embeddings mockeable inyectable opcional.
    embedding_provider: Any = None
    # Canal centralizado para el pipeline NLI (cargado en __post_init__)
    nli_pipeline: Any = None

    # Nota: El parámetro 'mode' (factual/hybrid/creative) ha sido eliminado.
    # La creatividad se controla exclusivamente mediante rigidity_epsilon.

    # El wrapper notario nunca debe bloquear, pero mantenemos el parámetro por compatibilidad.
    enable_hard_halt: bool = False

    # Trazabilidad externa opcional para auditorías y reportes.
    client_id: str | None = None
    trace_input: str | None = None

    # Mapeo configurable de campos de entrada (Standard-Zero Phases 1-4)
    input_field_audit: str = "audit_input"  # Fase 3: logits stream desde Llama
    input_field_context: str = "context_input"  # Fase 2: System Prompt (conditioning)
    input_field_user: str = "user_input"  # Fase 2: User Prompt (instruction) - NUEVO
    input_field_policies: str = "context_policies"  # Fase 1: Políticas para compilación

    # Configuración de Llama para Fase 1 (Cold Loop) y Fase 3 (Hot Loop)
    llama_model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct"
    llama_tokenizer: Any = None  # Se carga en __post_init__ si es necesario
    llama_model: Any = None  # Se carga en __post_init__ si es necesario

    # Procesador de logits para contención sub-simbólica (Fase 3)
    logits_processor: Any = None  # Se inicializa en __post_init__
    logits_processor_hard_only: bool = False  # Si True, solo bloquea políticas "hard"
    logits_processor_audit_trace: bool = False  # Si True, registra interceptiones

    # Matriz compilada de tokens prohibidos (W_bank) - Fase 1
    # Se genera automáticamente en __post_init__ desde context_policies
    w_bank: dict[int, tuple[str, int]] | None = None
    invariant_synthesizer: Any = None  # Instancia de InvariantSynthesizer

    # Control de compilación Cold/Hot Loop
    compile_policies_on_init: bool = True  # Si True, compila políticas durante __post_init__
    enable_logits_interception: bool = False  # Si True, inyecta procesador en generate()

    extra_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def _normalized_weights(self) -> tuple[float, ...]:
        """Devuelve los pesos de disonancia normalizados para garantizar una suma convexa (1.0)."""
        raw_weights = list(self.dissonance_weights)
        sum_w = sum(raw_weights)
        if sum_w == 0:
            return (0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return tuple(w / sum_w for w in raw_weights)

    def __post_init__(self) -> None:
        """
        Validaciones y normalizaciones post-inicialización.
        Implementa Fase 1 (Cold Loop): compilación de políticas → W_bank.
        """
        import os

        from idicoc_notary_core.utils.embedding_service import EmbeddingService

        # Configurar el proveedor de embeddings en el servicio central de forma inmediata.
        # Si no se especifica proveedor, esto borra cualquier proveedor previo compartido entre instancias.
        EmbeddingService.set_provider(self.embedding_provider)

        # Cargar pipeline NLI centralizado y exponerlo en la configuración
        try:
            from transformers import pipeline as hf_pipeline

            hf_token = os.getenv("HF_TOKEN")
            auth = hf_token if hf_token else True
            print(f"[Fase 1 - Cold Loop] Cargando pipeline NLI: {self.semantic_nli_model}")
            self.nli_pipeline = hf_pipeline(
                "zero-shot-classification",
                model=self.semantic_nli_model,
            )
        except Exception as e:
            import warnings

            warnings.warn(
                f"[Fase 1 - Cold Loop] No se pudo cargar pipeline NLI ({self.semantic_nli_model}): {e}. "
                "Operaciones basadas en NLI se omitirán.",
                UserWarning,
            )
            self.nli_pipeline = None

        # Asegurar que las rutas de persistencia relativas se resuelvan siempre respecto al directorio raíz del proyecto 'Idicoc_notary'
        package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

        # Calcular firma del modelo si no se proporciona
        if not self.embedding_signature:
            from idicoc_notary_core.utils.embedding_utils import compute_embedding_signature

            self.embedding_signature = compute_embedding_signature(self.semantic_embedding_model)

        if not os.path.isabs(self.ctm_nodes_path):
            self.ctm_nodes_path = os.path.abspath(os.path.join(package_root, self.ctm_nodes_path))
        if not os.path.isabs(self.ctm_root_path):
            self.ctm_root_path = os.path.abspath(os.path.join(package_root, self.ctm_root_path))

        if self.policy_loader is None:
            policy_path = self.policy_file_path
            if not os.path.isabs(policy_path):
                policy_path = os.path.abspath(os.path.join(package_root, policy_path))
            if os.path.exists(policy_path):
                from .graph.loader import FilePolicyLoader

                self.policy_loader = FilePolicyLoader(policy_path)

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

        # ─────────────────────────────────────────────────────────────────────
        # FASE 1 (COLD LOOP): Compilación de Políticas → W_bank
        # Se ejecuta UNA SOLA VEZ durante la inicialización del sistema
        # ─────────────────────────────────────────────────────────────────────
        if self.compile_policies_on_init:
            self._initialize_cold_loop()

        # El framework no fuerza normalización de embeddings; la coherencia de espacios queda a cargo del usuario.

    def _initialize_cold_loop(self) -> None:
        """
        Inicializa el bucle frío (Fase 1): carga políticas, Llama tokenizer, compila W_bank.
        """
        import os

        try:
            # Cargar políticas si existe policy_loader
            policies = []
            if self.policy_loader is not None:
                policies = self.policy_loader.load_policies()

            if not policies:
                # Sin políticas, se puede seguir funcionando (W_bank estará vacío)
                import warnings

                warnings.warn(
                    "[Fase 1 - Cold Loop] No se encontraron políticas. "
                    "W_bank estará vacío y no se aplicará contención.",
                    UserWarning,
                )
                self.w_bank = {}
                return

            # Cargar tokenizador de Llama si no está ya cargado
            if self.llama_tokenizer is None:
                try:
                    from transformers import AutoTokenizer

                    hf_token = os.getenv("HF_TOKEN")
                    auth_token = hf_token if hf_token else True
                    print(
                        f"[Fase 1 - Cold Loop] Cargando tokenizador Llama: {self.llama_model_name}"
                    )
                    self.llama_tokenizer = AutoTokenizer.from_pretrained(
                        self.llama_model_name,
                        cache_dir="models_cache",
                        token=auth_token,
                    )
                except Exception as e:
                    import warnings

                    warnings.warn(
                        f"[Fase 1 - Cold Loop] Error cargando tokenizador Llama: {e}. "
                        "Se omitirá compilación de W_bank.",
                        UserWarning,
                    )
                    self.w_bank = {}
                    return

            # Crear e inicializar InvariantSynthesizer
            from .graph.invariant_synthesizer import InvariantSynthesizer

            embedding_service = None
            try:
                # Intentar obtener el servicio de embeddings si está disponible
                embedding_service = EmbeddingService()
            except:
                pass  # Sin servicio de embeddings, igual funciona

            self.invariant_synthesizer = InvariantSynthesizer(
                tokenizer=self.llama_tokenizer,
                embedding_service=embedding_service,
            )

            # Compilar políticas → W_bank
            print(f"[Fase 1 - Cold Loop] Compilando {len(policies)} políticas...")
            self.w_bank = self.invariant_synthesizer.compile_policies(
                policies=policies,
                include_variants=True,
                hardness_multiplier=2.0,  # Políticas "hard" × 2 prioridad
            )

            # Log del reporte de compilación
            report = self.invariant_synthesizer.get_compilation_report()
            print(
                f"[Fase 1 - Cold Loop] ✓ Compilación completada. "
                f"W_bank size: {report['w_bank_size']}, "
                f"Políticas: success={report['successful']}, warnings={report['warnings']}, errors={report['errors']}"
            )

            # Inicializar Procesador de Logits (Fase 3) si se requiere interception
            if self.enable_logits_interception and self.w_bank:
                self._initialize_hot_loop_processor()

        except Exception as e:
            import warnings
            import traceback

            warnings.warn(
                f"[Fase 1 - Cold Loop] Error durante inicialización: {e}\n{traceback.format_exc()}",
                UserWarning,
            )

    def _initialize_hot_loop_processor(self) -> None:
        """
        Inicializa el Procesador de Logits para Fase 3 (Hot Loop).
        Se inyectará en la llamada model.generate() de Llama.
        """
        if not self.w_bank:
            import warnings

            warnings.warn(
                "[Fase 3 - Hot Loop] W_bank está vacío. "
                "No se inicializará procesador de logits.",
                UserWarning,
            )
            return

        try:
            from .dse.logits_processor import DeterministicMUXLogitsProcessor

            print(
                f"[Fase 3 - Hot Loop] Inicializando DeterministicMUXLogitsProcessor. "
                f"Tokens prohibidos: {len(self.w_bank)}"
            )

            self.logits_processor = DeterministicMUXLogitsProcessor(
                w_bank=self.w_bank,
                hard_only=self.logits_processor_hard_only,
                audit_trace=self.logits_processor_audit_trace,
            )

            print(f"[Fase 3 - Hot Loop] ✓ Procesador de logits inicializado.")

        except Exception as e:
            import warnings
            import traceback

            warnings.warn(
                f"[Fase 3 - Hot Loop] Error inicializando procesador: {e}\n{traceback.format_exc()}",
                UserWarning,
            )
