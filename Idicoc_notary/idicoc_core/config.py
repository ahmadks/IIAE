"""
Configuración del auditor IDICOC.
Contiene la configuración global del flujo de auditoría y los parámetros
específicos de cada modo de disonancia.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from idicoc_core.isg.loader import PolicyLoader

# Default configuration values
# NOTE: λ_1 (d_1: Axiom of Uniqueness) is a KL-divergence metric for probability
# distributions ONLY. For text LLM outputs, d_1 is always 0.0 (correct per formalism).
# Therefore λ_2 (d_2: policy graph violations) carries the primary weight for text auditing.
DEFAULT_DISSONANCE_WEIGHTS = (
    0.0,  # λ0: discrete edit distance (unused for text)
    0.0,  # λ1: KL-div to canonical state (only for distribution inputs)
    0.9,  # λ2: policy graph violations — primary metric for text auditing
    0.1,  # λ3: temporal constraint violations
    0.0,  # λ4: hash indexing (unused)
    0.0,  # λ5: consensus (unused)
    0.0,  # λ6: sealing/verification (unused)
)

DEFAULT_SEMANTIC_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_SEMANTIC_NLI_MODEL = "facebook/bart-large-mnli"
DEFAULT_SEMANTIC_NLI_CONFLICT_THRESHOLD = 0.5
DEFAULT_SEMANTIC_NLI_WARNING_THRESHOLD = 0.75
DEFAULT_SEMANTIC_MIN_RAG_SCORE = 0.1
DEFAULT_TERMINAL_RIGIDITY_THRESHOLD = 0.01
DEFAULT_EMBEDDING_MAX_CHUNKS = 10


@dataclass
class AuditConfig:
    """Configuración completa del auditor IDICOC."""

    # Tolerancias y umbrales configurables.
    correction_base_tolerance: float = 0.15
    rigidity_epsilon: float = 0.0
    allowed_epsilon: float = 0.15  # Added allowed_epsilon for new orchestrator design
    instance_name: str = "ai_comercial"

    # Paths de persistencia inyectables para CTM.
    ctm_nodes_path: str = "./tests/results/ctm_nodes.json"
    ctm_root_path: str = "./ctm_root.txt"
    ctm_wal_path: str | None = None  # Si es None, se deriva automáticamente de ctm_nodes_path
    hardware_key_env_var: str = "IIAE_HARDWARE_KEY"
    require_hardware_seal: bool = False

    # Configuración de backends de persistencia avanzados para CTM
    ctm_storage_backend: Any = "file"
    ctm_storage_kwargs: dict[str, Any] = field(default_factory=dict)

    # Pesos de disonancia
    dissonance_weights: tuple[float, float, float, float, float, float, float] = (
        DEFAULT_DISSONANCE_WEIGHTS
    )

    # Estrategia de disonancia inyectable.
    dissonance_strategy: Any = None

    # Parámetros específicos de evaluación semántica
    semantic_embedding_model: str = DEFAULT_SEMANTIC_EMBEDDING_MODEL
    semantic_nli_model: str = DEFAULT_SEMANTIC_NLI_MODEL
    semantic_nli_conflict_threshold: float = DEFAULT_SEMANTIC_NLI_CONFLICT_THRESHOLD
    semantic_nli_warning_threshold: float = DEFAULT_SEMANTIC_NLI_WARNING_THRESHOLD
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
    semantic_min_rag_score: float = DEFAULT_SEMANTIC_MIN_RAG_SCORE
    embedding_signature: str | None = None
    strict_embedding_signature: bool = False
    terminal_rigidity_threshold: float = DEFAULT_TERMINAL_RIGIDITY_THRESHOLD
    embedding_max_chunks: int = DEFAULT_EMBEDDING_MAX_CHUNKS

    ctm_mode: str = "full"

    # Sistema de inyección de politicas
    policy_loader: "PolicyLoader | None" = None
    policy_file_path: str = "policies.txt"

    # Proveedor de embeddings mockeable inyectable opcional.
    embedding_provider: Any = None
    # Canal centralizado para el pipeline NLI (cargado en __post_init__)
    nli_pipeline: Any = None

    # El wrapper notario nunca debe bloquear, pero mantenemos el parámetro por compatibilidad.
    enable_hard_halt: bool = False

    # Trazabilidad externa opcional para auditorías y reportes.
    client_id: str | None = None
    trace_input: str | None = None

    # Mapeo configurable de campos de entrada
    input_field_audit: str = "audit_input"
    input_field_context: str = "context_input"
    input_field_user: str = "user_input"
    input_field_policies: str = "context_policies"

    # Configuración del LLM
    llm_model_name: str = "microsoft/Phi-3.5-mini-instruct"
    llm_tokenizer: Any = None
    llm_model: Any = None

    # Campos heredados (llama_*) para compatibilidad con código anterior (Deprecated)
    llama_model_name: str | None = None
    llama_tokenizer: Any = None
    llama_model: Any = None

    # Procesador de logits
    logits_processor: Any = None
    logits_processor_hard_only: bool = False
    logits_processor_audit_trace: bool = False

    # Matriz compilada de tokens prohibidos
    w_bank: dict[int, tuple[str, int]] | None = None
    invariant_synthesizer: Any = None

    # Control de compilación Cold/Hot Loop
    compile_policies_on_init: bool = True
    enable_logits_interception: bool = False

    extra_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def _normalized_weights(self) -> tuple[float, ...]:
        raw_weights = list(self.dissonance_weights)
        sum_w = sum(raw_weights)
        if sum_w == 0:
            return (0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        return tuple(w / sum_w for w in raw_weights)

    def __post_init__(self) -> None:
        import os
        import warnings

        # Sync deprecated llama_* variables
        if self.llama_model_name is not None:
            warnings.warn(
                "llama_model_name está deprecado. Use llm_model_name en su lugar.",
                DeprecationWarning,
            )
            self.llm_model_name = self.llama_model_name
        if self.llama_tokenizer is not None:
            self.llm_tokenizer = self.llama_tokenizer
        if self.llama_model is not None:
            self.llm_model = self.llama_model

        from idicoc_core.utils.embedding_service import EmbeddingService

        # Set globally
        EmbeddingService.set_provider(self.embedding_provider)

        # Build NLI pipeline
        try:
            from transformers import pipeline as hf_pipeline

            hf_token = os.getenv("HF_TOKEN")
            auth = hf_token if hf_token else True
            force_update = os.getenv("IIAE_FORCE_UPDATE", "").lower() in ("true", "1", "yes")

            print(f"[Fase 1 - Cold Loop] Cargando pipeline NLI: {self.semantic_nli_model}")
            if force_update:
                self.nli_pipeline = hf_pipeline(
                    "zero-shot-classification",
                    model=self.semantic_nli_model,
                    token=auth,
                    local_files_only=False,
                )
            else:
                try:
                    self.nli_pipeline = hf_pipeline(
                        "zero-shot-classification",
                        model=self.semantic_nli_model,
                        token=auth,
                        local_files_only=True,
                    )
                except Exception:
                    self.nli_pipeline = hf_pipeline(
                        "zero-shot-classification",
                        model=self.semantic_nli_model,
                        token=auth,
                        local_files_only=False,
                    )
        except Exception as e:
            warnings.warn(
                f"[Fase 1 - Cold Loop] No se pudo cargar pipeline NLI ({self.semantic_nli_model}): {e}. "
                "Operaciones basadas en NLI se omitirán.",
                UserWarning,
            )
            self.nli_pipeline = None

        # Resolve paths
        package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        # Calculate signature
        if not self.embedding_signature:
            from idicoc_core.utils.embedding_utils import compute_embedding_signature

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
                from idicoc_core.isg.loader import FilePolicyLoader

                self.policy_loader = FilePolicyLoader(policy_path)

        if self.dissonance_strategy is None:
            from idicoc_core.dse.evaluator import StructuralDissonanceStrategy

            self.dissonance_strategy = StructuralDissonanceStrategy

        if self.enable_hard_halt:
            warnings.warn(
                "La opción enable_hard_halt ha sido forzada a False ya que "
                "el wrapper notario opera en modo pasivo y no debe bloquear el flujo.",
                UserWarning,
            )
            self.enable_hard_halt = False

        if self.compile_policies_on_init:
            self._initialize_cold_loop()

    def _initialize_cold_loop(self) -> None:
        import os

        try:
            policies = []
            if self.policy_loader is not None:
                policies = self.policy_loader.load_policies()

            if not policies:
                import warnings

                warnings.warn(
                    "[Fase 1 - Cold Loop] No se encontraron políticas. "
                    "W_bank estará vacío y no se aplicará contención.",
                    UserWarning,
                )
                self.w_bank = {}
                return

            if self.llm_tokenizer is None:
                try:
                    from transformers import AutoTokenizer

                    hf_token = os.getenv("HF_TOKEN")
                    auth_token = hf_token if hf_token else True
                    force_update = os.getenv("IIAE_FORCE_UPDATE", "").lower() in (
                        "true",
                        "1",
                        "yes",
                    )

                    print(f"[Fase 1 - Cold Loop] Cargando tokenizador LLM: {self.llm_model_name}")
                    if force_update:
                        self.llm_tokenizer = AutoTokenizer.from_pretrained(
                            self.llm_model_name,
                            cache_dir="models_cache",
                            token=auth_token,
                            local_files_only=False,
                        )
                    else:
                        try:
                            self.llm_tokenizer = AutoTokenizer.from_pretrained(
                                self.llm_model_name,
                                cache_dir="models_cache",
                                token=auth_token,
                                local_files_only=True,
                            )
                        except Exception:
                            self.llm_tokenizer = AutoTokenizer.from_pretrained(
                                self.llm_model_name,
                                cache_dir="models_cache",
                                token=auth_token,
                                local_files_only=False,
                            )
                except Exception as e:
                    import warnings

                    warnings.warn(
                        f"[Fase 1 - Cold Loop] Error cargando tokenizador LLM: {e}. "
                        "Se omitirá compilación de W_bank.",
                        UserWarning,
                    )
                    self.w_bank = {}
                    return

            from idicoc_core.isg.loader import InvariantSynthesizer
            from idicoc_core.utils.embedding_service import EmbeddingService

            embedding_service = None
            try:
                embedding_service = EmbeddingService()
            except:
                pass

            self.invariant_synthesizer = InvariantSynthesizer(
                tokenizer=self.llm_tokenizer,
                embedding_service=embedding_service,
            )

            print(f"[Fase 1 - Cold Loop] Compilando {len(policies)} políticas...")
            self.w_bank = self.invariant_synthesizer.compile_policies(
                policies=policies,
                include_variants=True,
                hardness_multiplier=2.0,
            )

            report = self.invariant_synthesizer.get_compilation_report()
            print(
                f"[Fase 1 - Cold Loop] ✓ Compilación completada. "
                f"W_bank size: {report['w_bank_size']}, "
                f"Políticas: success={report['successful']}, warnings={report['warnings']}, errors={report['errors']}"
            )

            if self.enable_logits_interception and self.w_bank:
                self._initialize_hot_loop_processor()

        except Exception as e:
            import warnings
            import traceback

            warnings.warn(
                f"[Fase 1 - Cold Loop] Error durante inicialización: {e}\n{traceback.format_exc()}",
                UserWarning,
            )
        finally:
            self.llama_model_name = self.llm_model_name
            self.llama_tokenizer = self.llm_tokenizer
            self.llama_model = self.llm_model

    def _initialize_hot_loop_processor(self) -> None:
        if not self.w_bank:
            import warnings

            warnings.warn(
                "[Fase 3 - Hot Loop] W_bank está vacío. "
                "No se inicializará procesador de logits.",
                UserWarning,
            )
            return

        try:
            from idicoc_core.dse.evaluator import DeterministicMUXLogitsProcessor

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
