from __future__ import annotations
import math
from typing import Any, List, Tuple
import numpy as np

def _cosine_distance(a: list | np.ndarray, b: list | np.ndarray) -> float:
    if len(a) != len(b):
        raise ValueError(
            f"Dimensionality mismatch between vectors: {len(a)} vs {len(b)}."
        )
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
    is_prob_target = np.all(target_state >= 0) and np.isclose(
        np.sum(target_state), 1.0, atol=1e-5
    )

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


def _compute_context_contradiction(
    y: Any, context_input: List[str], config: Any
) -> Tuple[float, List[str]]:
    """
    Computes semantic contradiction between audit_input and context rules via embedding cosine similarity.
    """
    if not context_input:
        return 0.0, []

    text_y = str(getattr(y, "content", getattr(y, "text_content", y)))
    if not text_y or str(text_y).strip() == "" or "array(" in text_y or "tensor(" in text_y:
        return 0.0, []

    try:
        from idicoc_notary.utils.embedding_service import EmbeddingService

        embed_service = EmbeddingService()
        model_name = getattr(
            config, "semantic_embedding_model", "sentence-transformers/all-MiniLM-L6-v2"
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

        max_contradiction = 0.0
        contradictory_contexts = []

        for ctx in context_input:
            if not ctx.strip():
                continue

            try:
                ctx_emb = _encode_text(ctx)
            except Exception:
                try:
                    ctx_emb = embedder.encode(ctx, convert_to_numpy=True)
                except TypeError:
                    ctx_emb = embedder.encode(ctx)

            ctx_emb = np.asarray(ctx_emb, dtype=float)
            similarity = np.dot(audit_emb, ctx_emb) / (
                np.linalg.norm(audit_emb) * np.linalg.norm(ctx_emb) + 1e-12
            )

            contradiction_score = float(1.0 - similarity)

            if contradiction_score > max_contradiction:
                max_contradiction = contradiction_score

            if contradiction_score > 0.4:
                contradictory_contexts.append(ctx)

        if not contradictory_contexts:
            return 0.0, []
        return max_contradiction, contradictory_contexts
    except Exception:
        return 0.0, []
