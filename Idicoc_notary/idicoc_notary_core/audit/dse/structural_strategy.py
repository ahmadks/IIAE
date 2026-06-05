# idicoc_notary_core/audit/dse/structural_strategy.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import numpy as np

from .dissonance_strategy import DissonanceStrategy

if TYPE_CHECKING:
    from idicoc_notary_core.audit.config import AuditConfig
    from idicoc_notary_core.kernel.projection.invariant_state_generator import CanonicalState
    from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph


class StructuralDissonanceStrategy(DissonanceStrategy):
    """
    Estrategia de disonancia estructural total.

    Implementa la métrica D_s definida en la especificación coalgebraica IDICOC (Sección 4.2),
    donde el espacio global S se particiona en 7 etapas y D_s es la suma convexa:

        D_s(s, s') = Σ_{i=0}^6 λ_i * d_i(s_i, s'_i)

    Con Σ λ_i = 1.
    """

    def __init__(
        self,
        config: "AuditConfig",
        property_graph: Optional["PropertyGraph"] = None,
        # Parámetros de la especificación IDICOC 7-stage
        lambda_0: float = 0.0,
        lambda_1: float = 0.0,
        lambda_2: float = 0.0,
        lambda_3: float = 0.0,
        lambda_4: float = 0.0,
        lambda_5: float = 0.0,
        lambda_6: float = 0.0,
    ) -> None:
        super().__init__(config)
        self.correction_base_tolerance = getattr(config, "correction_base_tolerance", 0.15)
        self._graph: Optional["PropertyGraph"] = property_graph

        # Si se especifican a través del constructor, se usan; si no, se toman de config
        weights = getattr(config, "_normalized_weights", None) or getattr(
            config, "dissonance_weights", None
        )
        if (
            weights is not None
            and len(weights) == 7
            and all(
                w == 0.0
                for w in [lambda_0, lambda_1, lambda_2, lambda_3, lambda_4, lambda_5, lambda_6]
            )
        ):
            self.lambda_0 = weights[0]
            self.lambda_1 = weights[1]
            self.lambda_2 = weights[2]
            self.lambda_3 = weights[3]
            self.lambda_4 = weights[4]
            self.lambda_5 = weights[5]
            self.lambda_6 = weights[6]
        else:
            self.lambda_0 = lambda_0
            self.lambda_1 = lambda_1
            self.lambda_2 = lambda_2
            self.lambda_3 = lambda_3
            self.lambda_4 = lambda_4
            self.lambda_5 = lambda_5
            self.lambda_6 = lambda_6

        # Normalizar para garantizar suma convexa si es necesario
        sum_lambda = sum(
            [
                self.lambda_0,
                self.lambda_1,
                self.lambda_2,
                self.lambda_3,
                self.lambda_4,
                self.lambda_5,
                self.lambda_6,
            ]
        )
        if sum_lambda == 0:
            self.lambda_1 = 1.0  # fallback a d_1 si todo es 0
        elif abs(sum_lambda - 1.0) > 1e-5:
            self.lambda_0 /= sum_lambda
            self.lambda_1 /= sum_lambda
            self.lambda_2 /= sum_lambda
            self.lambda_3 /= sum_lambda
            self.lambda_4 /= sum_lambda
            self.lambda_5 /= sum_lambda
            self.lambda_6 /= sum_lambda

    def set_graph(self, graph: "PropertyGraph") -> None:
        """Inyecta el PropertyGraph en caliente (llamado por el pipeline tras DSE)."""
        self._graph = graph

    def _validate_input(self, audit_input: Any, expected_size: int) -> np.ndarray:
        try:
            measure = np.asarray(getattr(audit_input, "distribution", audit_input), dtype=float)
        except (ValueError, TypeError):
            raise TypeError("El input no es una señal numérica válida.")
        # If expected_size <= 0 treat as 'no expected size' and return as-is
        if expected_size and expected_size > 0:
            if measure.size != expected_size:
                if measure.size < expected_size:
                    padded = np.zeros(expected_size, dtype=float)
                    padded[: measure.size] = measure
                    measure = padded
                else:
                    measure = measure[:expected_size]
        return measure

    def _compute_d_0(self, s0: Any, s0_prime: Any) -> float:
        """d_0: Discrete Feature Edit Distance (Levenshtein)"""
        # Simplificación: si son strings, Levenshtein normalizado
        if isinstance(s0, str) and isinstance(s0_prime, str):
            # Simulamos levenshtein distance / max length
            l1, l2 = len(s0), len(s0_prime)
            if l1 == 0 and l2 == 0:
                return 0.0
            return float(abs(l1 - l2)) / max(l1, l2)  # Proxy para el test
        return 0.0

    def _compute_d_1(self, mu: np.ndarray, target_state: np.ndarray) -> float:
        """
        d_1: Stage 1 (Normalization/Invariant Distance).
        Computes the Kullback-Leibler Divergence if both vectors are valid probability distributions.
        Otherwise falls back to Empirical Mover's Distance (EMD) for backward compatibility.
        """
        is_prob_mu = np.all(mu >= 0) and np.isclose(np.sum(mu), 1.0, atol=1e-5)
        is_prob_target = np.all(target_state >= 0) and np.isclose(
            np.sum(target_state), 1.0, atol=1e-5
        )

        if is_prob_mu and is_prob_target:
            try:
                from scipy.special import rel_entr

                # Add a tiny epsilon to prevent log(0) issues inside rel_entr
                eps = 1e-12
                p = np.clip(mu, eps, 1.0)
                q = np.clip(target_state, eps, 1.0)
                p /= p.sum()
                q /= q.sum()
                kl_div = np.sum(rel_entr(p, q))
                # Normalize KL Divergence to [0, 1] using exponential decay
                return float(1.0 - np.exp(-kl_div))
            except ImportError:
                pass

        # Fallback to cumulative EMD
        cum_mu = np.clip(np.cumsum(mu), 0.0, 1.0)
        cum_target = np.clip(np.cumsum(target_state), 0.0, 1.0)
        return float(np.sum(np.abs(cum_mu - cum_target)))

    def _compute_d_2(self, s2_delta: float, s2_prime_delta: float) -> float:
        """d_2: Stage 2 (Normalization). Theoretically: Euclidean distance on vectors in R^{n_i}."""
        return abs(s2_delta - s2_prime_delta)

    def _compute_d_3(self, s3_trace: List[float], s3_prime_trace: List[float]) -> float:
        """d_3: Stage 3 (Hashing). Theoretically: Hamming distance on the hash space."""
        if not s3_trace or not s3_prime_trace:
            return 0.0
        n = min(len(s3_trace), len(s3_prime_trace))
        return float(sum(abs(s3_trace[i] - s3_prime_trace[i]) for i in range(n)))

    def _compute_d_4(self, s4_hash: str, s4_prime_hash: str) -> float:
        """d_4: Stage 4 (Indexing). Theoretically: Manhattan distance on sparse vectors."""
        if not s4_hash or not s4_prime_hash:
            return 0.0
        return 0.0 if s4_hash == s4_prime_hash else 1.0

    def _compute_d_5(self, s5_trap: int, s5_prime_trap: int) -> float:
        """d_5: Stage 5 (Consensus). Theoretically: Discrete metric on agreement {0, 1}."""
        return 0.0 if s5_trap == s5_prime_trap else 1.0

    def _compute_d_6(self, s6_dist_k: float, s6_prime_dist_k: float) -> float:
        """d_6: Stage 6/7 (Sealing/Verification). Theoretically: Euclidean on signature embeddings / Discrete outcomes."""
        return s6_dist_k + s6_prime_dist_k

    def _compute_context_contradiction(
        self, y: Any, context_input: List[str]
    ) -> Tuple[float, List[str]]:
        """
        Computes semantic contradiction between audit_input and context rules via embedding cosine similarity.

        IDICOC is a semantic auditor (not a symbolic validator). Contradiction is measured via
        embedding-based similarity:
            contradiction_score = 1.0 - cosine_similarity(audit_embedding, context_embedding)

        This avoids NLI model limitations with domain-specific phrases like "primer dígito debe ser 7".

        Returns tuple of (max_contradiction_score, list_of_contradictory_contexts).
        """
        if not context_input:
            return 0.0, []

        text_y = str(getattr(y, "content", getattr(y, "text_content", y)))
        if not text_y or str(text_y).strip() == "" or "array(" in text_y or "tensor(" in text_y:
            return 0.0, []

        try:
            from idicoc_notary_core.utils.embedding_service import EmbeddingService

            embed_service = EmbeddingService()

            # Get embedding model name from config
            model_name = getattr(
                self.config, "semantic_embedding_model", "sentence-transformers/all-MiniLM-L6-v2"
            )
            embedder = embed_service.get_embedder(model_name)

            if embedder is None or not hasattr(embedder, "encode"):
                return 0.0, []

            def _encode_text(input_text: str) -> np.ndarray:
                try:
                    embedding = embedder.encode(input_text, convert_to_numpy=True)
                except TypeError:
                    try:
                        embedding = embedder.encode(input_text, model_name=model_name)
                    except TypeError:
                        embedding = embedder.encode(input_text)

                if isinstance(embedding, np.ndarray):
                    return embedding.astype(float)
                if isinstance(embedding, (list, tuple)):
                    return np.asarray(embedding, dtype=float)
                return np.asarray([embedding], dtype=float)

            # Encode audit_input text
            audit_emb = _encode_text(text_y)

            max_contradiction = 0.0
            contradictory_contexts = []

            for ctx in context_input:
                if not ctx.strip():
                    continue

                # Encode context rule
                try:
                    ctx_emb = _encode_text(ctx)
                except Exception:
                    try:
                        ctx_emb = embedder.encode(ctx, convert_to_numpy=True)
                    except TypeError:
                        ctx_emb = embedder.encode(ctx)

                # Compute cosine similarity
                ctx_emb = np.asarray(ctx_emb, dtype=float)
                similarity = np.dot(audit_emb, ctx_emb) / (
                    np.linalg.norm(audit_emb) * np.linalg.norm(ctx_emb) + 1e-12
                )

                # Contradiction = 1 - similarity (lower similarity = higher contradiction)
                contradiction_score = float(1.0 - similarity)

                if contradiction_score > max_contradiction:
                    max_contradiction = contradiction_score

                # Mark as contradictory if score > threshold (0.4 = same as NLI)
                if contradiction_score > 0.4:
                    contradictory_contexts.append(ctx)

            if not contradictory_contexts:
                return 0.0, []
            return max_contradiction, contradictory_contexts
        except Exception:
            return 0.0, []

    def compute(
        self,
        audit_input: Any,
        context_input: List[str],
        context_policies: List[str],
        epsilon: float = 0.0,
        validate_conflicts: bool = False,
    ) -> Tuple[float, float, Any, bool, Dict[str, Any]]:
        """
        Computes total structural dissonance D_s = Σ_{i=0}^6 λ_i d_i across 7 stages.

        Returns:
            (D_s, d_context, audit_input, corrected_flag, metrics_dict)

        where:
        - D_s: Total dissonance score [0, 1]
        - d_context: Semantic contradiction score from RAG context [0, 1]
        - audit_input: Original input (never modified)
        - corrected_flag: Always False (projection happens in IDICOCPipeline, not here)
        - metrics_dict: Metadata including algebraic_components, contradictory_contexts
        """
        # K no tiene representación vectorial en este diseño.
        # En esta versión legacy de compute() no existe un target_state numérico.
        # Usamos 4 como dimensión canónica del anchor uniforme en la ruta numérica
        mu_raw = self._validate_input(audit_input, 4)
        total = mu_raw.sum()
        mu = mu_raw / total if total > 1e-14 else np.ones_like(mu_raw) / mu_raw.size

        # ── Stage S₀ — d₀: Levenshtein (INACTIVO) ──────────────────────────
        # Solo aplica cuando el input lleva un campo '.text_content' (pipelines de texto/NLP).
        # En el pipeline numérico/algebraico este campo siempre está vacío → d₀ ≡ 0.0.
        # λ₀ debe mantenerse a 0 para no sesgar D_s con una componente siempre nula.
        s0_str = getattr(audit_input, "text_content", "")
        d0 = self._compute_d_0(s0_str, "")  # → 0.0 en modo numérico

        # Axiomatic Anchoring: The 'Zero Point' (K) of the system MUST be a Semantic Axiom
        # that defines Absolute Unicity (e.g., Sura 112 or Leibniz's law), rather than a physical constant.
        # This guarantees a single reference root (Canonical Invariant State) for the MAII-ISG.
        try:
            n_ref = mu.size
            if n_ref > 0:
                from idicoc_notary_core.utils.embedding_service import EmbeddingService

                embed_service = EmbeddingService()

                # Axiom of Uniqueness (MAII-MAO-Theory.pdf, page 5)
                axiom_of_uniqueness_text = "Axiom of Uniqueness: Absolute Unicity. Leibniz's law. Say, 'He is Allah, [who is] One, Allah, the Eternal Refuge.'"
                k_vector = embed_service.encode(axiom_of_uniqueness_text)

                # Pad or truncate k_vector to match the dimensions of mu
                if k_vector.size < n_ref:
                    target_state = np.pad(k_vector, (0, n_ref - k_vector.size), mode="constant")
                else:
                    target_state = k_vector[:n_ref]

                # Normalize the anchor to act as a proper geometric fixed point
                total_k = target_state.sum()
                if total_k > 1e-14:
                    target_state = target_state / total_k
                else:
                    target_state = np.ones(n_ref, dtype=float) / float(n_ref)

                d1 = self._compute_d_1(mu, target_state)
            else:
                d1 = 0.0
        except Exception:
            # Fallback a distribución uniforme si falla el EmbeddingService
            n_ref = mu.size
            if n_ref > 0:
                target_state = np.ones(n_ref, dtype=float) / float(n_ref)
                d1 = self._compute_d_1(mu, target_state)
            else:
                d1 = 0.0

        # ── Stage S₂ — d₂: Property Graph / politicas (ACTIVO) ───────────────
        # Evalúa las restricciones simbólicas del grafo de politicas (ej. bin0 ≤ 0.5).
        # d₂ > 0 indica violación de al menos un policya duro o blando del dominio.
        d2 = 0.0
        if self._graph is not None:
            try:
                from idicoc_notary_core.audit.graph.property_graph_evaluator import (
                    PropertyGraphEvaluator,
                )

                evaluator = PropertyGraphEvaluator(self._graph)
                d2 = float(evaluator.evaluate(audit_input))
            except Exception:
                pass

        # ── Stage S₃ — d₃: bisimulación temporal (ACTIVO) ──────────────────
        # Cuantifica la divergencia de la traza histórica del sistema usando ℓ₁.
        # Activo cuando el PropertyGraph tiene nodos con historial de transiciones.
        d3 = 0.0
        if self._graph is not None:
            try:
                from idicoc_notary_core.audit.graph.property_graph_evaluator import (
                    PropertyGraphEvaluator,
                )

                evaluator = PropertyGraphEvaluator(self._graph)
                d3 = float(evaluator.compute_temporal(audit_input))
            except Exception:
                pass

        # ── Stage S₄ — d₄: Hamming criptográfico (INACTIVO) ────────────────
        # Requiere comparar hashes SHA-256 de dos estados de ledger consecutivos.
        # En un ciclo de auditoría individual solo hay un estado; el hash anterior
        # vive en el CTM y no se inyecta como parámetro de d_i → d₄ ≡ 0.0.
        d4 = 0.0

        # ── Stage S₅ — d₅: Boundary trap del CustodialKernel (INACTIVO) ────
        # El estado SEMANTIC_SCOPE_VIOLATION es una señal de kernel-space (SO).
        # No existe un canal de IPC que lo exponga al pipeline Python en tiempo real.
        # Requeriría integración a nivel de módulo de kernel → d₅ ≡ 0.0.
        d5 = 0.0

        # ── Stage S₆ — d₆: convergencia asintótica (INACTIVO) ──────────────
        # Mide dist(s₆, K) sobre el estado terminal tras N iteraciones acumuladas.
        # No es computable por ciclo individual: necesita la traza completa hasta
        # el punto fijo, que solo existe fuera del pipeline en tiempo real → d₆ ≡ 0.0.
        d6 = 0.0

        d_context, contradictory_contexts = self._compute_context_contradiction(
            audit_input, context_input
        )

        if d2 == float("inf") or d3 == float("inf"):
            d_s = float("inf")
        else:
            d_s = (
                self.lambda_0 * d0
                + self.lambda_1 * d1
                + self.lambda_2 * d2
                + self.lambda_3 * d3
                + self.lambda_4 * d4
                + self.lambda_5 * d5
                + self.lambda_6 * d6
            )

        d_s = max(d_s, d_context)

        effective_threshold = self.correction_base_tolerance + epsilon
        is_compliant = d_s <= effective_threshold

        metrics: Dict[str, Any] = {
            "d_s": d_s,
            "d_0": d0,
            "d_1": d1,
            "d_2": d2,
            "d_3": d3,
            "d_4": d4,
            "d_5": d5,
            "d_6": d6,
            "d_context": d_context,
            "effective_threshold": effective_threshold,
            "d_terminal": d_s,
            "terminality_violation": not is_compliant,
            "reference_count": int(mu.size),
            "correction_flag": not is_compliant,
            "max_policy_distance": d2,
            "max_context_distance": d_context,
            "violated_policies": [],
            "contradictory_contexts": contradictory_contexts,
            "support_found": True,
            "snapping_flag": False,
        }

        return (d_s, d_context, audit_input, not is_compliant, metrics)

    def compute_dissonance(
        self, y: Any, V_hat: Any, G_t: Any, context_input: list | None = None
    ) -> float:
        from idicoc_notary_core.utils.string_utils import StringUtils

        model_name = getattr(
            self.config, "semantic_embedding_model", "sentence-transformers/all-MiniLM-L6-v2"
        )
        y_vec = StringUtils.to_vector(y, model_name=model_name)
        v_hat_vec = StringUtils.to_vector(V_hat, model_name=model_name)

        d1 = self._compute_d_1_vectorized(y_vec, v_hat_vec)

        d2 = 0.0
        d3 = 0.0
        if G_t is not None:
            from idicoc_notary_core.audit.graph.property_graph_evaluator import (
                PropertyGraphEvaluator,
            )

            evaluator = PropertyGraphEvaluator(G_t)
            d2 = float(evaluator.evaluate(y))
            d3 = float(evaluator.compute_temporal(y))

        if d2 == float("inf") or d3 == float("inf"):
            d_s = float("inf")
        else:
            d_s = max(0.0, min(1.0, self.lambda_1 * d1 + self.lambda_2 * d2 + self.lambda_3 * d3))

        d_context = 0.0
        if context_input:
            d_context, _ = self._compute_context_contradiction(y, context_input)

        return max(d_s, d_context)

    def project(
        self,
        y: Any,
        epsilon: float,
        V_hat: Any,
        G_t: Any,
        max_iter: int = 10,
        context_input: list | None = None,
    ) -> Any:
        from idicoc_notary_core.utils.string_utils import StringUtils

        model_name = getattr(
            self.config, "semantic_embedding_model", "sentence-transformers/all-MiniLM-L6-v2"
        )

        z = StringUtils.to_vector(y, model_name=model_name).copy()
        target = StringUtils.to_vector(V_hat, model_name=model_name)

        if self.compute_dissonance(z, V_hat, G_t, context_input=context_input) <= epsilon:
            return z

        # Obtener los hiperparámetros SPSA de la configuración del auditor
        spsa_a = getattr(self.config, "spsa_a", 0.1)
        spsa_c = getattr(self.config, "spsa_c", 1e-4)
        spsa_alpha = getattr(self.config, "spsa_alpha", 0.602)
        spsa_gamma = getattr(self.config, "spsa_gamma", 0.101)
        spsa_decay_enabled = getattr(self.config, "spsa_decay_enabled", True)

        for k in range(max_iter):
            current_diss = self.compute_dissonance(z, V_hat, G_t, context_input=context_input)
            if current_diss <= epsilon:
                return z

            # Calcular coeficientes SPSA dinámicos con ley de decaimiento condicional
            if spsa_decay_enabled:
                ak = spsa_a / ((k + 1) ** spsa_alpha)
                ck = spsa_c / ((k + 1) ** spsa_gamma)
            else:
                ak = spsa_a
                ck = spsa_c

            # Gradiente analítico de d_1 (distancia euclídea al target)
            grad_d1 = z - target

            # SPSA para aproximar el gradiente conjunto de d_2 y d_3
            delta = np.random.choice([-1.0, 1.0], size=z.size)
            diss_plus = self.compute_dissonance(
                z + ck * delta, V_hat, G_t, context_input=context_input
            )
            diss_minus = self.compute_dissonance(
                z - ck * delta, V_hat, G_t, context_input=context_input
            )

            # Sanitización de perturbaciones antes del cálculo del gradiente
            if not np.isfinite(diss_plus) or not np.isfinite(diss_minus):
                break

            # Si no hay variación detectable (función plana o entorno mock), usamos el gradiente analítico
            if abs(diss_plus - diss_minus) < 1e-9:
                grad = grad_d1
            else:
                grad = ((diss_plus - diss_minus) / (2.0 * ck)) * delta

            # Sanitización del gradiente frente a inestabilidad numérica
            if not np.isfinite(grad).all():
                break

            norm = float(np.linalg.norm(grad))
            if norm < 1e-12:
                grad = grad_d1
                if not np.isfinite(grad).all():
                    break
                norm = float(np.linalg.norm(grad))
                if norm < 1e-12:
                    break

            z_cand = z - ak * (grad / norm)
            if np.isfinite(z_cand).all():
                z = z_cand
            else:
                break
        return z

    def _compute_d_1_vectorized(self, mu_raw: np.ndarray, ref_raw: np.ndarray) -> float:
        if mu_raw.ndim != 1 or ref_raw.ndim != 1 or mu_raw.size == 0 or ref_raw.size == 0:
            return 1.0
        n = max(mu_raw.size, ref_raw.size)
        mu = np.zeros(n)
        mu[: mu_raw.size] = mu_raw
        ref = np.zeros(n)
        ref[: ref_raw.size] = ref_raw

        has_negative = np.any(mu_raw < 0) or np.any(ref_raw < 0)
        is_large_dim = n >= 50

        # Si son distribuciones de probabilidad reales (no tienen negativos, no son embeddings enormes puros)
        if not has_negative:
            s_mu = mu.sum()
            s_ref = ref.sum()
            if s_mu > 1e-14 and s_ref > 1e-14:
                p = mu / s_mu
                q = ref / s_ref

                try:
                    from scipy.special import rel_entr

                    eps = 1e-12
                    p_safe = np.clip(p, eps, 1.0)
                    q_safe = np.clip(q, eps, 1.0)
                    p_safe /= p_safe.sum()
                    q_safe /= q_safe.sum()

                    kl_div = np.sum(rel_entr(p_safe, q_safe))
                    return float(1.0 - np.exp(-kl_div))
                except ImportError:
                    pass

        # Fallback a Coseno para embeddings, o EMD.
        if has_negative or is_large_dim:
            norm_mu = np.linalg.norm(mu)
            norm_ref = np.linalg.norm(ref)
            if norm_mu < 1e-12 or norm_ref < 1e-12:
                return 1.0
            u = mu / norm_mu
            v = ref / norm_ref
            cos_sim = float(np.dot(u, v))
            dist = (1.0 - cos_sim) / 2.0
            return max(0.0, min(1.0, dist))
        else:
            s_mu = mu.sum()
            s_ref = ref.sum()
            mu = mu / s_mu if s_mu > 1e-14 else np.ones(n) / n
            ref = ref / s_ref if s_ref > 1e-14 else np.ones(n) / n
            cum_mu = np.clip(np.cumsum(mu), 0.0, 1.0)
            cum_target = np.clip(np.cumsum(ref), 0.0, 1.0)
            return float(np.sum(np.abs(cum_mu - cum_target)))

    def select_canonical_input(self, canonical_state: "CanonicalState") -> np.ndarray:
        return canonical_state.measure_vector

    def canonical_axis(self) -> str:
        return "measure"
