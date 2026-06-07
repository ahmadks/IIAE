"""
Configuración del auditor IDICOC.
Contiene la configuración global del flujo de auditoría y los parámetros
específicos de cada modo de disonancia.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

import os

if TYPE_CHECKING:
    from idicoc_core.isg.loader import PolicyLoader

# ── Rutas por defecto ────────────────────────────────────────────────────────
_DEFAULT_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_CTM_NODES_PATH = os.path.join(_DEFAULT_BASE, "tests", "results", "ctm_nodes.json")
_DEFAULT_CTM_ROOT_PATH = os.path.join(_DEFAULT_BASE, "ctm_root.txt")
_DEFAULT_SPSA_TRACES_DIR = os.path.join(_DEFAULT_BASE, "tests", "results", "spsa_traces")

# ── Pesos de disonancia por defecto ─────────────────────────────────────────
# NOTE: λ_1 (d_1: Axiom of Uniqueness) es KL-divergence sólo para distribuciones
# de probabilidad. Para salidas de texto LLM, d_1 = 0.0 (correcto por formalismo).
# Por eso λ_2 (d_2: violaciones del grafo) lleva el peso principal en texto.
DEFAULT_DISSONANCE_WEIGHTS = (
    0.0,  # λ0: distancia de edición discreta (no usada para texto)
    0.2,  # λ1: KL-div al estado canónico (solo para entradas de distribución)
    0.5,  # λ2: violaciones del grafo de políticas — métrica principal para texto
    0.3,  # λ3: violaciones de restricciones temporales
    0.0,  # λ4: indexación por hash (no usada)
    0.0,  # λ5: consenso (no usado)
    0.0,  # λ6: sellado/verificación (no usado)
)

DEFAULT_SEMANTIC_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_SEMANTIC_NLI_MODEL = "facebook/bart-large-mnli"

_NLI_PIPELINES_CACHE: dict[str, Any] = {}


@dataclass
class AuditConfig:
    """Configuración completa del auditor IDICOC."""

    # ── 1. Umbrales de decisión ──────────────────────────────────────────────
    # correction_base_tolerance: umbral base D_s ≤ base + epsilon → ADMITTED
    correction_base_tolerance: float = 0.15
    # rigidity_epsilon: epsilon adicional inyectable por llamada (legado, se mapea a allowed_epsilon)
    rigidity_epsilon: float = 0.0
    # allowed_epsilon: epsilon efectivo usado por el pipeline
    allowed_epsilon: float = 0.15

    # ── 2. Parámetros RAG / Integridad de contexto ───────────────────────────
    # λ_context ∈ [0,1]: peso de d_context en D_s.
    #   D_s = (1 - λ_context) × D_policy + λ_context × d_context
    #   0.0 → el RAG no influye; 1.0 → solo RAG; 0.4 → equilibrio recomendado.
    lambda_context: float = 0.4

    # Umbral de alerta para etiquetar un chunk RAG como "contradictorio".
    # Solo afecta el etiquetado en trazabilidad, NO el valor numérico de d_context.
    #   0.20 → muy estricto; 0.35 → moderado (defecto); 0.50 → permisivo.
    rag_contradiction_alert_threshold: float = 0.35

    # Similitud coseno mínima entre un chunk RAG y una política HARD para
    # considerar ese chunk como "crítico" en _is_chunk_critical.
    rag_critical_chunk_similarity_threshold: float = 0.6

    # Penalización por omisión: cuando el LLM no incluye todo el contexto RAG
    # pero tampoco lo contradice (soft omission, no hard contradiction).
    omission_penalty: float = 0.05

    # Similitud coseno mínima entre el output LLM y el chunk primario del RAG
    # para considerar que el "hecho principal" está presente en la respuesta.
    rag_primary_presence_threshold: float = 0.70

    # Factor de reducción del coverage_score para chunks no-críticos del RAG.
    rag_non_critical_coverage_damper: float = 0.1

    # Factor de reducción del coverage_score cuando el hecho primario está presente.
    rag_primary_present_coverage_damper: float = 0.3

    # Umbral de contradicción HARD: si max_contradiction_score supera este valor
    # se aplica penalización fuerte directa (d_context = max_contradiction_score).
    rag_hard_contradiction_threshold: float = 0.8

    # Factor de contribución del coverage_score a d_context cuando no hay
    # contradicción hard: d_context = coverage_score * factor.
    rag_coverage_contribution_factor: float = 0.2

    # Límite superior (cap) de d_context para respetar el umbral de corrección.
    rag_d_context_cap: float = 0.15

    # ── 2.5 Thresholds de Estabilidad y SPSA (Stage 6) ───────────────────────
    diss_threshold_green: float = 0.10      # Aceptación automática
    diss_threshold_red: float = 0.25        # Hard Halt (Bloqueo)
    spsa_convergence_epsilon: float = 0.08   # Umbral objetivo para convergencia
    spsa_max_iters: int = 5                  # Iteraciones máximas
    enforce_unit_norm: bool = True          # Normalización L2 unitaria
    spsa_a: float = 0.1                      # Parámetro de ganancia de SPSA (step size)
    spsa_c: float = 0.05                     # Parámetro de perturbación de SPSA
    max_rag_divergence: float = 0.35         # Cerca forense: Máxima divergencia RAG permitida durante SPSA
    spsa_trace_dir: str = _DEFAULT_SPSA_TRACES_DIR



    # ── 3. Pesos de disonancia y estrategia ─────────────────────────────────
    dissonance_weights: tuple[float, float, float, float, float, float, float] = (
        DEFAULT_DISSONANCE_WEIGHTS
    )

    # Multiplicador de peso para políticas con hardness=hard en el evaluador.
    policy_hard_weight_multiplier: float = 2.0

    # ── 4. Embeddings y NLI ──────────────────────────────────────────────────
    semantic_embedding_model: str = DEFAULT_SEMANTIC_EMBEDDING_MODEL
    semantic_nli_model: str = DEFAULT_SEMANTIC_NLI_MODEL

    # Umbral de score NLI para clasificar una respuesta como contradicción.
    semantic_nli_conflict_threshold: float = 0.5

    # Firma del modelo de embeddings para verificación de integridad.
    embedding_signature: str | None = None
    # Si True, rechaza la configuración cuando la firma del embedder no coincide.
    strict_embedding_signature: bool = False
    # Número máximo de chunks en que se divide un texto largo antes de embeberse.
    embedding_max_chunks: int = 10

    # Proveedor de embeddings inyectable (mock en tests, modelo real en producción).
    embedding_provider: Any = None
    # Pipeline NLI cargado en __post_init__ (no configurar manualmente).
    nli_pipeline: Any = None

    # ── 5. ISG: políticas ────────────────────────────────────────────────────
    policy_loader: "PolicyLoader | None" = None
    policy_file_path: str = "policies.txt"

    # ── 6. CTM: trazabilidad criptográfica ───────────────────────────────────
    ctm_mode: str = "full"  # "full" | "disabled"
    ctm_nodes_path: str = _DEFAULT_CTM_NODES_PATH
    ctm_root_path: str = _DEFAULT_CTM_ROOT_PATH
    ctm_wal_path: str | None = None  # None → se deriva de ctm_nodes_path
    hardware_key_env_var: str = "IIAE_HARDWARE_KEY"
    require_hardware_seal: bool = False
    record_k_fingerprint: bool = True

    # ── 7. Hot Loop: logits interception (LLM en tiempo real) ───────────────
    # Habilita la interceptación de logits durante la generación del LLM.
    enable_logits_interception: bool = False
    # El procesador de logits compilado (se inicializa en _initialize_hot_loop_processor).
    logits_processor: Any = None
    # Si True, solo aplica la máscara a tokens marcados como hard.
    logits_processor_hard_only: bool = False
    # Si True, registra un audit trail de cada intercepción de logits.
    logits_processor_audit_trace: bool = False

    # ── 8. Cold Loop: compilación de políticas en W_bank ────────────────────
    compile_policies_on_init: bool = True
    # Banco de tokens prohibidos compilados {token_id: (hardness, priority)}.
    w_bank: dict[int, tuple[str, int]] | None = None
    invariant_synthesizer: Any = None

    # ── 9. LLM (tokenizador para compilación de W_bank) ─────────────────────
    # Estos campos sólo se usan durante _initialize_cold_loop para compilar W_bank.
    llm_model_name: str = "microsoft/Phi-3.5-mini-instruct"
    llm_tokenizer: Any = None
    llm_model: Any = None

    # Campos deprecados (compatibilidad con código anterior que usaba llama_*)
    llama_model_name: str | None = None
    llama_tokenizer: Any = None
    llama_model: Any = None

    # ── 10. Metadatos de instancia ───────────────────────────────────────────
    instance_name: str = "ai_comercial"

    # ── 11. Compatibilidad / legado ──────────────────────────────────────────
    # enable_hard_halt: el wrapper notario nunca bloquea (forzado a False en __post_init__).
    enable_hard_halt: bool = False

    # ── Propiedad calculada ──────────────────────────────────────────────────
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

        # Sincronizar campos deprecados llama_* → llm_*
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

        EmbeddingService.set_provider(self.embedding_provider)

        # Cargar / cachear pipeline NLI
        global _NLI_PIPELINES_CACHE
        if self.semantic_nli_model in _NLI_PIPELINES_CACHE:
            self.nli_pipeline = _NLI_PIPELINES_CACHE[self.semantic_nli_model]
        else:
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
                _NLI_PIPELINES_CACHE[self.semantic_nli_model] = self.nli_pipeline
            except Exception as e:
                warnings.warn(
                    f"[Fase 1 - Cold Loop] No se pudo cargar pipeline NLI "
                    f"({self.semantic_nli_model}): {e}. Operaciones NLI se omitirán.",
                    UserWarning,
                )
                self.nli_pipeline = None

        # Resolver rutas relativas
        package_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

        # Calcular firma del modelo de embeddings si no se proporcionó
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
            except Exception:
                pass

            self.invariant_synthesizer = InvariantSynthesizer(
                tokenizer=self.llm_tokenizer,
                embedding_service=embedding_service,
            )

            print(f"[Fase 1 - Cold Loop] Compilando {len(policies)} políticas...")
            self.w_bank = self.invariant_synthesizer.compile_policies(
                policies=policies,
                include_variants=True,
                hardness_multiplier=self.policy_hard_weight_multiplier,
            )

            report = self.invariant_synthesizer.get_compilation_report()
            print(
                f"[Fase 1 - Cold Loop] ✓ Compilación completada. "
                f"W_bank size: {report['w_bank_size']}, "
                f"Políticas: success={report['successful']}, "
                f"warnings={report['warnings']}, errors={report['errors']}"
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
            # Mantener sincronización de campos deprecados
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

            print("[Fase 3 - Hot Loop] ✓ Procesador de logits inicializado.")

        except Exception as e:
            import warnings
            import traceback

            warnings.warn(
                f"[Fase 3 - Hot Loop] Error inicializando procesador: {e}\n{traceback.format_exc()}",
                UserWarning,
            )
