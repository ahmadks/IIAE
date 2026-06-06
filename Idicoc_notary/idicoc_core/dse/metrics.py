from __future__ import annotations
import math
from typing import Any, List, Tuple
import numpy as np


def _cosine_distance(a: list | np.ndarray, b: list | np.ndarray) -> float:
    if len(a) != len(b):
        raise ValueError(f"Dimensionality mismatch between vectors: {len(a)} vs {len(b)}.")
    dot = sum(x * z for x, z in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a < 1e-12 or norm_b < 1e-12:
        return 1.0
    cosine_sim = dot / (norm_a * norm_b)
    return 1.0 - max(-1.0, min(1.0, cosine_sim))


def _compute_d_0(s0: Any, s0_prime: Any) -> float:
    """d_0: Discrete Feature Edit Distance (Levenshtein)"""
    if isinstance(s0, str) and isinstance(s0_prime, str):
        l1, l2 = len(s0), len(s0_prime)
        if l1 == 0 and l2 == 0:
            return 0.0
        return float(abs(l1 - l2)) / max(l1, l2)
    return 0.0


def _compute_d_1(mu: np.ndarray, target_state: np.ndarray) -> float:
    """d_1: Stage 1 (Normalization/Invariant Distance)."""
    is_prob_mu = np.all(mu >= 0) and np.isclose(np.sum(mu), 1.0, atol=1e-5)
    is_prob_target = np.all(target_state >= 0) and np.isclose(np.sum(target_state), 1.0, atol=1e-5)

    if is_prob_mu and is_prob_target:
        try:
            from scipy.special import rel_entr

            eps = 1e-12
            p = np.clip(mu, eps, 1.0)
            q = np.clip(target_state, eps, 1.0)
            p /= p.sum()
            q /= q.sum()
            kl_div = np.sum(rel_entr(p, q))
            return float(1.0 - np.exp(-kl_div))
        except ImportError:
            pass

    cum_mu = np.clip(np.cumsum(mu), 0.0, 1.0)
    cum_target = np.clip(np.cumsum(target_state), 0.0, 1.0)
    return float(np.sum(np.abs(cum_mu - cum_target)))


def _compute_d_1_vectorized(mu_raw: np.ndarray, ref_raw: np.ndarray) -> float:
    if mu_raw.ndim != 1 or ref_raw.ndim != 1 or mu_raw.size == 0 or ref_raw.size == 0:
        return 1.0
    n = max(mu_raw.size, ref_raw.size)
    mu = np.zeros(n)
    mu[: mu_raw.size] = mu_raw
    ref = np.zeros(n)
    ref[: ref_raw.size] = ref_raw

    has_negative = np.any(mu_raw < 0) or np.any(ref_raw < 0)
    is_large_dim = n >= 50

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


def _compute_d_2(s2_delta: float, s2_prime_delta: float) -> float:
    """d_2: Stage 2 (Normalization)"""
    return abs(s2_delta - s2_prime_delta)


def _compute_d_3(s3_trace: List[float], s3_prime_trace: List[float]) -> float:
    """d_3: Stage 3 (Hashing)"""
    if not s3_trace or not s3_prime_trace:
        return 0.0
    n = min(len(s3_trace), len(s3_prime_trace))
    return float(sum(abs(s3_trace[i] - s3_prime_trace[i]) for i in range(n)))


def _compute_d_4(s4_hash: str, s4_prime_hash: str) -> float:
    """d_4: Stage 4 (Indexing)"""
    if not s4_hash or not s4_prime_hash:
        return 0.0
    return 0.0 if s4_hash == s4_prime_hash else 1.0


def _compute_d_5(s5_trap: int, s5_prime_trap: int) -> float:
    """d_5: Stage 5 (Consensus)"""
    return 0.0 if s5_trap == s5_prime_trap else 1.0


def _compute_d_6(s6_dist_k: float, s6_prime_dist_k: float) -> float:
    """d_6: Stage 6/7 (Sealing/Verification)"""
    return s6_dist_k + s6_prime_dist_k


def _is_chunk_critical(ctx: str, evaluator: Any) -> bool:
    if evaluator is None or not hasattr(evaluator, "graph") or not evaluator.graph:
        return False
    # Get all hard policies in the graph
    hard_policies = [ax for ax in evaluator.graph.nodes.values() if ax.get("hardness") == "hard"]
    if not hard_policies:
        return False
    
    # Try to encode ctx for semantic similarity checks
    ctx_emb = None
    try:
        from idicoc_core.utils.embedding_service import EmbeddingService
        embed_service = EmbeddingService()
        ctx_emb = embed_service.encode(ctx)
    except Exception:
        pass
    
    import re
    for ax in hard_policies:
        a_type = ax.get("policy_type", "fact")
        if a_type in ("regex", "numeric"):
            pattern = ax.get("pattern", ax.get("text", ""))
            if pattern:
                try:
                    if re.search(pattern, ctx, re.IGNORECASE):
                        return True
                except Exception:
                    pass
        elif ctx_emb is not None:
            ax_emb = ax.get("embedding")
            if ax_emb is not None:
                try:
                    ctx_emb_arr = np.asarray(ctx_emb, dtype=float)
                    ax_emb_arr = np.asarray(ax_emb, dtype=float)
                    norm_a = np.linalg.norm(ctx_emb_arr)
                    norm_b = np.linalg.norm(ax_emb_arr)
                    if norm_a > 1e-12 and norm_b > 1e-12:
                        sim = float(np.dot(ctx_emb_arr / norm_a, ax_emb_arr / norm_b))
                        if sim >= 0.6:
                            return True
                except Exception:
                    pass
    return False


def _compute_context_contradiction(
    y: Any, context_input: List[str], config: Any, user_prompt: str = "", evaluator: Any = None
) -> Tuple[float, List[str]]:
    """
    Middleware de Integridad RAG→LLM: mide la disonancia de fase entre la
    "verdad recuperada" (context_input) y la respuesta generada por el LLM (y).

    Retorna (d_context, contradictory_contexts) donde:
      - d_context ∈ [0, 1]: distancia coseno máxima entre el output del LLM y
        cualquier chunk del contexto RAG. Equivale a la Disonancia de Fase Semántica.
        0.0 = coherencia perfecta con el RAG, 1.0 = contradicción total.
      - contradictory_contexts: chunks del RAG que superan el umbral de alerta.

    Si no hay context_input, el sistema está "ciego" y retorna 0.0 (sin penalización).
    """
    if not context_input:
        return 0.0, []

    import numpy as np
    # Si la entrada es un array numérico, distribución o lista de números, no se realiza
    # análisis semántico de contradicción RAG→LLM ya que no representa texto en lenguaje natural.
    if (
        isinstance(y, np.ndarray)
        or hasattr(y, "distribution")
        or (isinstance(y, list) and len(y) > 0 and isinstance(y[0], (int, float, np.number)))
    ):
        return 0.0, []

    text_y = str(getattr(y, "content", getattr(y, "text_content", y)))
    
    # También ignorar representaciones de arrays/listas de floats en formato string
    trimmed = text_y.strip()
    if trimmed.startswith("[") and trimmed.endswith("]"):
        try:
            import ast
            parsed = ast.literal_eval(trimmed)
            if isinstance(parsed, (list, tuple)) and len(parsed) > 0 and isinstance(parsed[0], (int, float)):
                return 0.0, []
        except Exception:
            pass

    if not text_y or str(text_y).strip() == "" or "array(" in text_y or "tensor(" in text_y:
        return 0.0, []

    # Umbral de alerta leído desde config (ver AuditConfig.rag_contradiction_alert_threshold).
    # Controla qué chunks del RAG se etiquetan como "contradictorios" en el log.
    # NO afecta al valor numérico de d_context ni al veredicto ADMITTED/REJECTED.
    contradiction_alert_threshold = float(
        getattr(config, "rag_contradiction_alert_threshold", 0.35)
    )

    try:
        from idicoc_core.config import DEFAULT_SEMANTIC_EMBEDDING_MODEL
        from idicoc_core.utils.embedding_service import EmbeddingService

        embed_service = EmbeddingService()
        model_name = getattr(
            config,
            "semantic_embedding_model",
            DEFAULT_SEMANTIC_EMBEDDING_MODEL,
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

        audit_emb = _encode_text(text_y)
        audit_norm = np.linalg.norm(audit_emb)
        if audit_norm < 1e-12:
            return 0.0, []
        audit_emb = audit_emb / audit_norm

        prompt_emb = None
        if user_prompt:
            try:
                prompt_emb = _encode_text(user_prompt)
                prompt_norm = np.linalg.norm(prompt_emb)
                if prompt_norm > 1e-12:
                    prompt_emb = prompt_emb / prompt_norm
                else:
                    prompt_emb = None
            except Exception:
                pass

        context_embs = []
        for ctx in context_input:
            if not ctx.strip():
                context_embs.append(None)
                continue
            try:
                ctx_emb = _encode_text(ctx)
                ctx_norm = np.linalg.norm(ctx_emb)
                if ctx_norm > 1e-12:
                    context_embs.append(ctx_emb / ctx_norm)
                else:
                    context_embs.append(None)
            except Exception:
                context_embs.append(None)

        # 1. Determine if the primary fact is present
        primary_idx = 0
        if prompt_emb is not None and len(context_embs) > 1:
            prompt_similarities = []
            for c_emb in context_embs:
                if c_emb is not None:
                    prompt_similarities.append(float(np.dot(prompt_emb, c_emb)))
                else:
                    prompt_similarities.append(-1.0)
            primary_idx = int(np.argmax(prompt_similarities))

        is_primary_present = False
        if primary_idx < len(context_embs) and context_embs[primary_idx] is not None:
            primary_sim = float(np.dot(audit_emb, context_embs[primary_idx]))
            is_primary_present = primary_sim >= 0.70

        max_similarity = -1.0
        min_similarity = 1.0
        max_contradiction_score = 0.0
        max_coverage_score = 0.0
        contradictory_contexts = []

        for idx, ctx in enumerate(context_input):
            if idx >= len(context_embs) or context_embs[idx] is None:
                continue

            ctx_emb = context_embs[idx]
            similarity = float(np.dot(audit_emb, ctx_emb))
            similarity = max(-1.0, min(1.0, similarity))

            if similarity > max_similarity:
                max_similarity = similarity
            if similarity < min_similarity:
                min_similarity = similarity

            is_contradiction = False
            
            # 1. Try NLI pipeline first
            nli_pipeline = getattr(config, "nli_pipeline", None)
            if nli_pipeline is not None:
                try:
                    nli_res = nli_pipeline(
                        sequences=text_y,
                        candidate_labels=["entailment", "contradiction", "neutral"],
                        hypothesis_template=f"Based on the context: {ctx}, this statement is {{}}."
                    )
                    idx_contra = nli_res["labels"].index("contradiction")
                    score_contra = nli_res["scores"][idx_contra]
                    top_label = nli_res["labels"][0]
                    nli_threshold = float(getattr(config, "semantic_nli_conflict_threshold", 0.5))
                    if top_label == "contradiction" or score_contra > nli_threshold:
                        is_contradiction = True
                except Exception as nli_err:
                    import logging
                    logging.getLogger(__name__).warning(f"Error calling NLI pipeline for contradiction check: {nli_err}")

            # 2. Fallback to embedding distance/similarity
            contradiction_score = float(1.0 - similarity)
            if not is_contradiction:
                if getattr(config, "nli_pipeline", None) is None:
                    if similarity < 0.0 and contradiction_score > contradiction_alert_threshold:
                        is_contradiction = True
                else:
                    if (similarity < 0.0 or len(context_input) == 1) and contradiction_score > contradiction_alert_threshold:
                        is_contradiction = True

            if is_contradiction:
                contradictory_contexts.append(ctx)
                max_contradiction_score = max(max_contradiction_score, contradiction_score)
            else:
                coverage_score = 1.0 - max(0.0, similarity)
                is_critical = _is_chunk_critical(ctx, evaluator)
                if not is_critical:
                    coverage_score *= 0.1
                elif is_primary_present:
                    coverage_score *= 0.3
                max_coverage_score = max(max_coverage_score, coverage_score)

        # d_context is the maximum of the two distances, bounded between 0.0 and 1.0
        d_context = max(max_coverage_score, max_contradiction_score, max(0.0, -min_similarity))
        d_context = max(0.0, min(1.0, d_context))

        return d_context, contradictory_contexts
    except Exception:
        return 0.0, []

