from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from idicoc_core.utils.logger import get_logger

logger = get_logger("dse.spsa")


class SPSACorrector:
    def __init__(self, config: Any) -> None:
        self.config = config

    def project(
        self,
        y_vec: np.ndarray,
        v_hat_vec: np.ndarray,
        const_metrics: Dict[str, Any],
        context_embs: Optional[List[np.ndarray]] = None,
    ) -> Tuple[np.ndarray, float, List[Dict[str, Any]]]:
        if context_embs is None:
            context_embs = []

        z = np.copy(np.asarray(y_vec, dtype=float))
        norm_z = np.linalg.norm(z)
        if norm_z > 1e-12:
            z = z / norm_z

        v_hat = np.asarray(v_hat_vec, dtype=float)
        norm_v = np.linalg.norm(v_hat)
        if norm_v > 1e-12:
            v_hat = v_hat / norm_v

        weights = self.config._normalized_weights
        lambda_1 = weights[1]
        lambda_2 = weights[2]
        lambda_3 = weights[3]

        const_d2 = const_metrics.get("d_logic", 0.0)
        # d_3 semantics now map to RAG/context; use d_context as the third term
        const_d_context = const_metrics.get("d_context", 0.0)
        lambda_context = float(getattr(self.config, "lambda_context", 0.4))

        def _cost_function(vec: np.ndarray) -> float:
            norm_val = np.linalg.norm(vec)
            vec_norm = vec / norm_val if norm_val > 1e-12 else vec

            dist = float(np.linalg.norm(vec_norm - v_hat))
            d1 = float(np.clip(dist / 2.0, 0.0, 1.0))

            # Combine uniqueness (d1) and policy dissonance (d_logic) as policy component,
            # and treat the d_context (RAG) as the lambda-weighted context term.
            policy_diss = lambda_1 * d1 + lambda_2 * const_d2
            d_s_val = (1.0 - lambda_context) * policy_diss + lambda_context * const_d_context
            return max(d_s_val, const_d_context * lambda_context)

        best_z = np.copy(z)
        best_loss = _cost_function(z)
        history = []
        init_rag_div = float(self._compute_rag_divergence(z, context_embs)) if context_embs else 0.0
        history.append(
            {
                "iteration": 0,
                "dissonance": float(best_loss),
                "rag_divergence": init_rag_div,
                "backtracked": False,
            }
        )

        if best_loss <= self.config.diss_threshold_green:
            return best_z, best_loss, history

        a = getattr(self.config, "spsa_a", 0.1)
        c = getattr(self.config, "spsa_c", 0.05)
        max_iters = self.config.spsa_max_iters
        max_rag_div_threshold = getattr(self.config, "max_rag_divergence", 0.35)

        for k in range(max_iters):
            delta = np.random.choice([-1.0, 1.0], size=z.size)
            z_plus = z + c * delta
            z_minus = z - c * delta

            loss_plus = _cost_function(z_plus)
            loss_minus = _cost_function(z_minus)

            diff = loss_plus - loss_minus
            grad = (diff / (2.0 * c)) * delta
            z_next = z - a * grad

            norm_next = np.linalg.norm(z_next)
            if norm_next > 1e-12:
                z_next = z_next / norm_next

            current_rag_div = 0.0
            backtracked = False
            if context_embs:
                current_rag_div = float(self._compute_rag_divergence(z_next, context_embs))
                if current_rag_div > max_rag_div_threshold:
                    backtracked = True
                    history.append(
                        {
                            "iteration": k + 1,
                            "dissonance": float(_cost_function(z_next)),
                            "rag_divergence": current_rag_div,
                            "backtracked": True,
                        }
                    )
                    continue

            loss_next = _cost_function(z_next)
            history.append(
                {
                    "iteration": k + 1,
                    "dissonance": float(loss_next),
                    "rag_divergence": current_rag_div,
                    "backtracked": backtracked,
                }
            )

            if loss_next < best_loss:
                best_loss = loss_next
                best_z = np.copy(z_next)

            z = z_next
            if best_loss <= self.config.diss_threshold_green:
                break

        return best_z, best_loss, history

    def _compute_rag_divergence(self, vec: np.ndarray, context_embs: List[np.ndarray]) -> float:
        max_sim = -1.0
        for c_emb in context_embs:
            if c_emb is None:
                continue
            sim = float(np.dot(vec, c_emb))
            if sim > max_sim:
                max_sim = sim
        return 0.0 if max_sim == -1.0 else 1.0 - max_sim

    def should_apply_correction(self, d_s: float, raw_metrics: Dict[str, Any]) -> bool:
        """
        Decide whether SPSA correction should be attempted based on dissonance metrics.
        Returns True if d_s is in the "gray band" for correction.
        """
        d2 = float(raw_metrics.get("d_2", 0.0))
        d3 = float(raw_metrics.get("d_3", 0.0))

        # Do not attempt SPSA when any discrete violation exists.
        if d2 > 0.0 or d3 > 0.0:
            return False

        if d_s == float("inf"):
            return False

        # Do not apply SPSA if there are no active policies in the graph.
        if raw_metrics.get("policy_graph_empty", False):
            logger.warning(
                "Skipping SPSA: active policy graph is empty. "
                "d_2 and d_3 are zero by default when no policies exist."
            )
            return False

        # SPSA is only allowed in the gray band for d_s
        in_ds_gray = self.config.diss_threshold_green < d_s <= self.config.diss_threshold_red
        return in_ds_gray

    def attempt_correction(
        self,
        llm_output: str,
        y_vector: np.ndarray,
        v_hat_vector: np.ndarray,
        raw_metrics: Dict[str, Any],
        effective_threshold: float,
    ) -> Optional[float]:
        """
        Attempt SPSA correction on LLM output.
        Returns corrected dissonance if successful, None otherwise.
        """
        import time

        t_spsa_start = time.perf_counter()
        try:
            corrected_vector, corrected_loss, history = self.project(
                y_vector,
                v_hat_vector,
                raw_metrics,
                context_embs=raw_metrics.get("context_embeddings", []),
            )

            raw_metrics["spsa_history"] = history
            t_spsa_elapsed = time.perf_counter() - t_spsa_start
            logger.info("[TIMING] SPSA correction: %.3f sec", t_spsa_elapsed)
            raw_metrics["spsa_duration_sec"] = t_spsa_elapsed
            return float(corrected_loss)

        except Exception as exc:
            logger.error(f"Error during SPSA correction: {exc}", exc_info=True)
            raw_metrics["spsa_error"] = str(exc)
            t_spsa_elapsed = time.perf_counter() - t_spsa_start
            logger.error("[TIMING] SPSA error after %.3f sec: %s", t_spsa_elapsed, exc)
            return None
