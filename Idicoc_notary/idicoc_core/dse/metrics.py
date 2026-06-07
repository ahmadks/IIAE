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
    """d_0: Discrete Feature Edit Distance"""
    if isinstance(s0, str) and isinstance(s0_prime, str):
        l1, l2 = len(s0), len(s0_prime)
        if l1 == 0 and l2 == 0:
            return 0.0
        return float(abs(l1 - l2)) / max(l1, l2)
    return 0.0


def _compute_d_1(mu: np.ndarray, target_state: np.ndarray) -> float:
    """d_1: Stage 1 (Normalization/Invariant Distance). Kantorovich-Rubinstein proxy."""
    is_prob_mu = np.all(mu >= 0) and np.isclose(np.sum(mu), 1.0, atol=1e-5)
    is_prob_target = np.all(target_state >= 0) and np.isclose(np.sum(target_state), 1.0, atol=1e-5)

    if is_prob_mu and is_prob_target:
        try:
            from scipy.special import rel_entr

            eps = 1e-12
            p, q = np.clip(mu, eps, 1.0), np.clip(target_state, eps, 1.0)
            p /= p.sum()
            q /= q.sum()
            return float(1.0 - np.exp(-np.sum(rel_entr(p, q))))
        except ImportError:
            pass

    cum_mu = np.clip(np.cumsum(mu), 0.0, 1.0)
    cum_target = np.clip(np.cumsum(target_state), 0.0, 1.0)
    return float(np.sum(np.abs(cum_mu - cum_target)))


def _compute_d_1_vectorized(mu_raw: np.ndarray, ref_raw: np.ndarray) -> float:
    if mu_raw.ndim != 1 or ref_raw.ndim != 1 or mu_raw.size == 0 or ref_raw.size == 0:
        return 1.0
    n = max(mu_raw.size, ref_raw.size)
    mu, ref = np.zeros(n), np.zeros(n)
    mu[: mu_raw.size] = mu_raw
    ref[: ref_raw.size] = ref_raw

    has_negative = np.any(mu_raw < 0) or np.any(ref_raw < 0)
    is_large_dim = n >= 50

    if not has_negative:
        s_mu, s_ref = mu.sum(), ref.sum()
        if s_mu > 1e-14 and s_ref > 1e-14:
            try:
                from scipy.special import rel_entr

                p_safe, q_safe = np.clip(mu / s_mu, 1e-12, 1.0), np.clip(ref / s_ref, 1e-12, 1.0)
                p_safe /= p_safe.sum()
                q_safe /= q_safe.sum()
                return float(1.0 - np.exp(-np.sum(rel_entr(p_safe, q_safe))))
            except ImportError:
                pass

    if has_negative or is_large_dim:
        norm_mu, norm_ref = np.linalg.norm(mu), np.linalg.norm(ref)
        if norm_mu < 1e-12 or norm_ref < 1e-12:
            return 1.0
        dist = (1.0 - float(np.dot(mu / norm_mu, ref / norm_ref))) / 2.0
        return max(0.0, min(1.0, dist))
    else:
        s_mu, s_ref = mu.sum(), ref.sum()
        mu = mu / s_mu if s_mu > 1e-14 else np.ones(n) / n
        ref = ref / s_ref if s_ref > 1e-14 else np.ones(n) / n
        cum_mu = np.clip(np.cumsum(mu), 0.0, 1.0)
        cum_target = np.clip(np.cumsum(ref), 0.0, 1.0)
        return float(np.sum(np.abs(cum_mu - cum_target)))


def _is_chunk_critical(ctx: str, evaluator: Any) -> bool:
    if evaluator is None or not hasattr(evaluator, "graph") or not evaluator.graph:
        return False
    hard_policies = [ax for ax in evaluator.graph.nodes.values() if ax.get("hardness") == "hard"]
    if not hard_policies:
        return False

    ctx_emb = None
    try:
        from idicoc_core.utils.embedding_service import EmbeddingService

        ctx_emb = EmbeddingService().encode(ctx)
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
        elif ctx_emb is not None and ax.get("embedding") is not None:
            try:
                ctx_arr, ax_arr = np.asarray(ctx_emb, dtype=float), np.asarray(
                    ax.get("embedding"), dtype=float
                )
                norm_a, norm_b = np.linalg.norm(ctx_arr), np.linalg.norm(ax_arr)
                if norm_a > 1e-12 and norm_b > 1e-12:
                    sim = float(np.dot(ctx_arr / norm_a, ax_arr / norm_b))
                    if sim >= float(
                        getattr(evaluator.config, "rag_critical_chunk_similarity_threshold", 0.6)
                    ):
                        return True
            except Exception:
                pass
    return False


def _compute_d_3(
    y: Any, context_input: List[str], config: Any, user_prompt: str = "", evaluator: Any = None
) -> Tuple[float, List[str]]:
    """
    d_3: Disonancia Externa (Contradicción RAG).
    Evalúa la divergencia factual de la señal contra los anclajes de contexto.
    """
    if not context_input:
        return 0.0, []

    if (
        isinstance(y, np.ndarray)
        or hasattr(y, "distribution")
        or (isinstance(y, list) and len(y) > 0 and isinstance(y[0], (int, float, np.number)))
    ):
        return 0.0, []

    text_y = str(getattr(y, "content", getattr(y, "text_content", y))).strip()
    if not text_y or text_y.startswith("[") or "array(" in text_y or "tensor(" in text_y:
        return 0.0, []

    alert_thresh = float(getattr(config, "rag_contradiction_alert_threshold", 0.35))
    primary_thresh = float(getattr(config, "rag_primary_presence_threshold", 0.70))
    non_crit_damper = float(getattr(config, "rag_non_critical_coverage_damper", 0.1))
    omission_penalty = float(getattr(config, "omission_penalty", 0.05))
    hard_contra_thresh = float(getattr(config, "rag_hard_contradiction_threshold", 0.8))
    cov_factor = float(getattr(config, "rag_coverage_contribution_factor", 0.2))
    cap = float(getattr(config, "rag_d_context_cap", 1.0))
    nli_thresh = float(getattr(config, "semantic_nli_conflict_threshold", 0.5))

    try:
        from idicoc_core.utils.embedding_service import EmbeddingService

        model_name = getattr(config, "semantic_embedding_model", "all-MiniLM-L6-v2")
        embedder = EmbeddingService().get_embedder(model_name)
        if embedder is None or not hasattr(embedder, "encode"):
            return 0.0, []

        def _enc(t: str) -> np.ndarray:
            try:
                e = embedder.encode(t, convert_to_numpy=True)
            except:
                e = embedder.encode(t)
            return e.astype(float) if isinstance(e, np.ndarray) else np.asarray(e, dtype=float)

        audit_emb = _enc(text_y)
        audit_norm = np.linalg.norm(audit_emb)
        if audit_norm < 1e-12:
            return 0.0, []
        audit_emb /= audit_norm

        ctx_embs = []
        for ctx in context_input:
            if not ctx.strip():
                ctx_embs.append(None)
                continue
            e = _enc(ctx)
            n = np.linalg.norm(e)
            ctx_embs.append(e / n if n > 1e-12 else None)

        is_primary_present = False
        if user_prompt and len(ctx_embs) > 1:
            try:
                p_emb = _enc(user_prompt)
                p_norm = np.linalg.norm(p_emb)
                if p_norm > 1e-12:
                    sims = [
                        float(np.dot(p_emb / p_norm, c)) if c is not None else -1.0
                        for c in ctx_embs
                    ]
                    idx = int(np.argmax(sims))
                    if ctx_embs[idx] is not None:
                        is_primary_present = (
                            float(np.dot(audit_emb, ctx_embs[idx])) >= primary_thresh
                        )
            except:
                pass

        max_contra, max_cov = 0.0, 0.0
        contradictions = []

        nli_pipeline = getattr(config, "nli_pipeline", None)

        for idx, ctx in enumerate(context_input):
            if ctx_embs[idx] is None:
                continue
            sim = max(-1.0, min(1.0, float(np.dot(audit_emb, ctx_embs[idx]))))
            is_contra = False
            c_score = 1.0 - sim

            if nli_pipeline:
                try:
                    res = nli_pipeline(
                        sequences=text_y,
                        candidate_labels=["entailment", "contradiction", "neutral"],
                        hypothesis_template=f"Based on: {ctx}, this is {{}}.",
                    )
                    if (
                        res["labels"][0] == "contradiction"
                        or res["scores"][res["labels"].index("contradiction")] > nli_thresh
                    ):
                        is_contra = True
                except:
                    pass

            if (
                not is_contra
                and (
                    (not nli_pipeline and sim < 0.0)
                    or (nli_pipeline and (sim < 0.0 or len(context_input) == 1))
                )
                and c_score > alert_thresh
            ):
                is_contra = True

            if is_contra:
                contradictions.append(ctx)
                max_contra = max(max_contra, c_score)
            else:
                cov = (1.0 - max(0.0, sim)) * (
                    1.0 if _is_chunk_critical(ctx, evaluator) else non_crit_damper
                )
                max_cov = max(max_cov, cov)

        if max_contra > hard_contra_thresh:
            d3_val = 1.0
        elif is_primary_present and not contradictions:
            d3_val = omission_penalty
        else:
            d3_val = max(max_cov * cov_factor, omission_penalty)

        return min(cap, max(0.0, d3_val)), contradictions
    except Exception:
        return 0.0, []
