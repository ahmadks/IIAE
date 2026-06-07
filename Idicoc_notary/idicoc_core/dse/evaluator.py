import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass

import numpy as np
import torch
from transformers import LogitsProcessor

from idicoc_core.isg.graph_manager import PropertyGraph
from idicoc_core.api.schemas import SessionContext
from idicoc_core.utils.logger import get_logger
from idicoc_core.utils.string_utils import StringUtils
from idicoc_core.dse.metrics import (
    _compute_d_1,
    _compute_d_1_vectorized,
    _compute_d_3,
    _cosine_distance,
)

logger = get_logger("dse.evaluator")


@dataclass
class DissonanceEvaluationResult:
    d_s: float
    d_1: float = 0.0
    d_2: float = 0.0
    d_3: float = 0.0
    violations: Optional[List[str]] = None
    correction_flag: bool = False
    corrected_output: Any = None
    metrics: Optional[Dict[str, Any]] = None


class DimensionalityMismatchError(ValueError):
    pass


class PropertyGraphEvaluator:
    """
    Evalúa el Grafo de Propiedades (d_2).
    Unifica restricciones lógicas, semánticas y temporales en una única dimensión de disonancia interna.
    """

    def __init__(self, graph: PropertyGraph, config: Any = None):
        self.graph = graph
        self.config = config

    def evaluate(
        self,
        y: Any,
        return_violations: bool = False,
    ) -> float | Tuple[float, List[Dict[str, Any]]]:
        """Evalúa TODAS las políticas del grafo.

        Por compatibilidad con llamadas legacy, devuelve d_2 por defecto.
        Si `return_violations` es True, devuelve `(d_2, violations)`.
        """
        if not self.graph or not self.graph.nodes:
            return (0.0, []) if return_violations else 0.0

        y_tokens = self._tokenize(self._to_str(y))
        y_vec = self._to_vec(y)
        now = datetime.now(timezone.utc)

        total_weight = 0.0
        weighted_penalty = 0.0
        violations = []
        has_hard_violation = False

        for ax in self.graph.nodes.values():
            if not self._policy_matches_mode(ax, y):
                continue

            # Ruteo unificado: Tiempo o Lógica
            if ax.get("policy_type") == "temporal":
                raw_penalty = self._temporal_penalty(ax, now)
            else:
                raw_penalty = self._logical_penalty(y, y_tokens, y_vec, ax)

            if raw_penalty > 0.0:
                hardness = ax.get("hardness", "hard")
                if hardness == "hard":
                    has_hard_violation = True
                violations.append(
                    {
                        "id": ax.get("id"),
                        "text": ax.get("text", ax.get("description", "")),
                        "hardness": hardness,
                        "penalty": raw_penalty,
                    }
                )

            weight = self._policy_weight(ax, self.config)
            weighted_penalty += raw_penalty * weight
            total_weight += weight

        d_2 = (
            float("inf")
            if has_hard_violation
            else (min(1.0, weighted_penalty / total_weight) if total_weight > 0 else 0.0)
        )
        return (d_2, violations) if return_violations else d_2

    def get_violated_policies(self, y: Any) -> List[Dict[str, Any]]:
        """Compatibility helper for legacy policy violation inspection."""
        return self.evaluate(y, return_violations=True)[1]

    @staticmethod
    def _to_str(y: Any) -> str:
        if y is None:
            return ""
        if isinstance(y, str):
            return y
        if isinstance(y, np.ndarray):
            return str(y.tolist())
        if isinstance(y, (list, tuple)):
            return str(list(y))
        return str(getattr(y, "source_text", getattr(y, "data", y)))

    @staticmethod
    def _input_mode(y: Any) -> str:
        if hasattr(y, "payload_type"):
            return str(getattr(y, "payload_type") or "all").lower()
        if isinstance(y, str):
            return "semantic"
        if isinstance(y, (list, tuple)) or isinstance(y, np.ndarray) or hasattr(y, "distribution"):
            return "numeric"
        return "semantic"

    def _policy_matches_mode(self, policy: Dict[str, Any], y: Any) -> bool:
        pmode = str(policy.get("mode", "all")).lower()
        if pmode == "all":
            return True
        imode = self._input_mode(y)
        return pmode in (imode, "all")

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        return {t for t in re.split(r"[\s,;:.!?()\[\]{}'\"]+", text.lower()) if t}

    @staticmethod
    def _to_vec(y: Any) -> Optional[list]:
        try:
            c = getattr(y, "measure_vector", getattr(y, "distribution", y))
            if isinstance(c, str):
                nums = [float(m.group(0)) for m in re.finditer(r"[-+]?[0-9]*\.?[0-9]+", c)]
                if nums:
                    return nums
            arr = np.asarray(c, dtype=float)
            if arr.ndim == 1 and arr.size > 0:
                return arr.tolist()
        except:
            pass
        return None

    def _evaluate_regex(self, ax: dict, y: Any) -> float:
        text_y = self._to_str(y)
        pattern = ax.get("pattern", ax.get("text", ""))
        if not pattern:
            return 0.0
        try:
            match = re.search(pattern, text_y, re.IGNORECASE)
        except re.error:
            match = re.search(pattern, text_y)
        return (
            (0.0 if match else 1.0)
            if ax.get("polarity", "affirmative") == "affirmative"
            else (1.0 if match else 0.0)
        )

    def _logical_penalty(
        self, y: Any, y_tokens: Set[str], y_vec: Optional[list], policy: Dict[str, Any]
    ) -> float:
        if policy.get("policy_type", "fact") in ("regex", "numeric"):
            return self._evaluate_regex(policy, y)

        from idicoc_core.utils.embedding_service import EmbeddingService

        embed_service = EmbeddingService()

        ax_emb = policy.get("embedding")
        if ax_emb is None:
            text = " ".join(
                str(policy.get(k, ""))
                for k in ["source_text", "subject", "predicate", "object"]
                if policy.get(k)
            )
            ax_emb = embed_service.encode(text).tolist()
            policy["embedding"] = ax_emb

        if y_vec is None or len(y_vec) != len(ax_emb):
            y_vec = embed_service.encode(self._to_str(y)).tolist()

        similarity = 1.0 - _cosine_distance(y_vec, ax_emb)
        return (
            1.0 - similarity
            if policy.get("polarity", "affirmative") == "affirmative"
            else similarity
        )

    def _temporal_penalty(self, policy: Dict[str, Any], now: datetime) -> float:
        def _parse(v):
            if v is None:
                return None
            if isinstance(v, datetime):
                return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
            if isinstance(v, (int, float)):
                return datetime.fromtimestamp(float(v), tz=timezone.utc)
            try:
                dt = datetime.fromisoformat(str(v))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except:
                return None

        v_from, v_until = _parse(policy.get("valid_from")), _parse(policy.get("valid_until"))
        ttl = policy.get("ttl_seconds")

        if not v_until and ttl:
            base = v_from or _parse(policy.get("timestamp"))
            if base:
                from datetime import timedelta

                v_until = base + timedelta(seconds=float(ttl))

        if not v_from and not v_until:
            return 0.0
        window = (
            max(1.0, float(ttl))
            if ttl
            else (max(1.0, (v_until - v_from).total_seconds()) if v_until and v_from else 86400.0)
        )

        if v_from and now < v_from:
            return 2.0 / (1.0 + math.exp(-((v_from - now).total_seconds()) / window)) - 1.0
        if v_until and now > v_until:
            return 2.0 / (1.0 + math.exp(-((now - v_until).total_seconds()) / window)) - 1.0
        return 0.0

    @staticmethod
    def _policy_weight(policy: Dict[str, Any], config: Any = None) -> float:
        priority = max(1, min(10, int(policy.get("priority", 1))))
        return (priority / 10.0) * (
            float(getattr(config, "policy_hard_weight_multiplier", 2.0))
            if policy.get("hardness") == "hard"
            else 1.0
        )


class DeterministicMUXLogitsProcessor(LogitsProcessor):
    def __init__(
        self,
        forbidden_token_ids: Optional[Any] = None,
        device: str = "cpu",
        w_bank: Optional[Dict[int, Tuple[str, int]]] = None,
        hard_only: bool = False,
        audit_trace: bool = False,
        cuda_device: Optional[str] = None,
    ) -> None:
        self.hard_only = hard_only
        self.audit_trace = audit_trace
        if forbidden_token_ids is None:
            self.forbidden_token_ids = (
                {tid for tid, (h, _) in w_bank.items() if h == "hard"}
                if (w_bank and hard_only)
                else (set(w_bank.keys()) if w_bank else set())
            )
        else:
            self.forbidden_token_ids = set(forbidden_token_ids)

        self.mask_tensor = torch.tensor(
            list(self.forbidden_token_ids), device=(cuda_device or device), dtype=torch.long
        )
        self.intercepts_log, self.intercepts_count = ([] if audit_trace else None), 0

    def __call__(
        self, _input_ids: torch.LongTensor, scores: torch.FloatTensor
    ) -> torch.FloatTensor:
        if self.mask_tensor.numel() > 0:
            scores[:, self.mask_tensor] = -float("inf")
        if self.audit_trace and self.intercepts_log is not None:
            self.intercepts_log.append(
                {
                    "iteration": self.intercepts_count,
                    "forbidden_count": len(self.forbidden_token_ids),
                }
            )
            self.intercepts_count += 1
        return scores

    def process_logits(self, logits: np.ndarray | torch.Tensor, _input_ids: Any = None) -> Any:
        is_numpy = isinstance(logits, np.ndarray)
        scores = torch.tensor(logits, dtype=torch.float32) if is_numpy else logits
        was_1d = scores.dim() == 1
        if was_1d:
            scores = scores.unsqueeze(0)
        scores = self.__call__(None, scores)
        if was_1d:
            scores = scores[0]
        return scores.detach().cpu().numpy() if is_numpy else scores


class StructuralDissonanceStrategy:
    """Compatibilidad con la estrategia de disonancia estructural."""

    def __init__(
        self,
        config: Any,
        lambda_1: float = 0.0,
        lambda_2: float = 0.0,
        lambda_3: float = 0.0,
    ):
        self.config = config
        self.lambda_1 = float(lambda_1)
        self.lambda_2 = float(lambda_2)
        self.lambda_3 = float(lambda_3)
        self._anchor = np.array([0.25, 0.25, 0.25, 0.25], dtype=float)

    def _normalize_distribution(self, distribution: np.ndarray) -> Tuple[np.ndarray, int]:
        arr = np.asarray(distribution, dtype=float)
        if arr.ndim != 1:
            arr = arr.flatten()

        if arr.size < 4:
            padded = np.zeros(4, dtype=float)
            padded[: arr.size] = arr
            arr = padded
        elif arr.size > 4:
            arr = arr[:4]

        arr = np.clip(arr, 0.0, None)
        total = float(np.sum(arr))
        if total <= 1e-12:
            arr = np.ones_like(arr, dtype=float) / float(arr.size)
        else:
            arr = arr / total
        return arr, arr.size

    def _input_distribution(self, audit_input: Any) -> np.ndarray:
        if hasattr(audit_input, "distribution"):
            return np.asarray(getattr(audit_input, "distribution"), dtype=float)
        if isinstance(audit_input, (list, tuple, np.ndarray)):
            return np.asarray(audit_input, dtype=float)
        if hasattr(audit_input, "data"):
            return np.asarray(getattr(audit_input, "data"), dtype=float)
        return np.asarray([], dtype=float)

    def _compute_effective_threshold(self, epsilon: float = 0.0) -> float:
        return float(getattr(self.config, "correction_base_tolerance", 0.15)) + float(epsilon)

    def compute(
        self,
        audit_input: Any,
        context_input: Any,
        context_policies: Any,
        epsilon: float = 0.0,
        validate_conflicts: bool = False,
    ) -> Tuple[float, float, Any, bool, Dict[str, Any]]:
        distribution = self._input_distribution(audit_input)
        normalized, reference_count = self._normalize_distribution(distribution)

        d_1 = float(_compute_d_1_vectorized(normalized, self._anchor))
        d_2 = 0.0
        d_3 = 0.0

        d_s = float(
            np.clip(self.lambda_1 * d_1 + self.lambda_2 * d_2 + self.lambda_3 * d_3, 0.0, 1.0)
        )
        effective_threshold = self._compute_effective_threshold(epsilon)
        correction_flag = bool(d_s > effective_threshold)

        metrics = {
            "d_1": d_1,
            "d_2": d_2,
            "d_3": d_3,
            "effective_threshold": effective_threshold,
            "terminality_violation": correction_flag,
            "reference_count": reference_count,
            "lambda_1": self.lambda_1,
            "lambda_2": self.lambda_2,
            "lambda_3": self.lambda_3,
        }

        corrected_output = normalized.tolist() if isinstance(normalized, np.ndarray) else normalized
        return d_s, d_1, corrected_output, correction_flag, metrics

    def compute_dissonance(self, audit_input: Any, anchor_input: Any, graph: Any) -> float:
        candidate_vec = np.asarray(
            StringUtils.to_vector(
                audit_input,
                model_name=getattr(self.config, "semantic_embedding_model", "all-MiniLM-L6-v2"),
            ),
            dtype=float,
        )
        anchor_vec = np.asarray(
            StringUtils.to_vector(
                anchor_input,
                model_name=getattr(self.config, "semantic_embedding_model", "all-MiniLM-L6-v2"),
            ),
            dtype=float,
        )

        d_1 = float(_compute_d_1_vectorized(candidate_vec, anchor_vec))
        d2_result = PropertyGraphEvaluator(graph, self.config).evaluate(
            audit_input, return_violations=True
        )
        d_2 = float(d2_result[0])
        d_3 = 0.0
        return float(
            np.clip(self.lambda_1 * d_1 + self.lambda_2 * d_2 + self.lambda_3 * d_3, 0.0, 1.0)
        )


class DissonanceStateEvaluator:
    """
    Notario IDICOC Unificado: D_s = w1(d1) + w2(d2) + w3(d3)
    d1: Proyección | d2: Grafo Interno | d3: Contexto RAG Externo
    """

    def __init__(self, config: Any):
        self.config = config
        self.strategy = StructuralDissonanceStrategy(config)

    def evaluate(
        self, llm_output: str, session_context: SessionContext, active_graph: PropertyGraph
    ) -> Tuple[float, List[str], Dict[str, Any]]:
        context_input = (
            [ctx.strip() for ctx in session_context.rag_context.split("\n") if ctx.strip()]
            if session_context.rag_context
            else []
        )
        eval_input = llm_output
        try:
            if isinstance(llm_output, str) and (
                llm_output.startswith("[") or "array" in llm_output
            ):
                import ast

                parsed = ast.literal_eval(llm_output)
                if isinstance(parsed, (list, tuple)):
                    eval_input = np.array(parsed, dtype=float)
        except:
            pass

        _eval_text = (
            eval_input
            if isinstance(eval_input, str)
            else str(
                getattr(
                    eval_input, "source_text", getattr(eval_input, "text_content", str(eval_input))
                )
            )
        )
        logger.info(f"[DSE] Evaluando: {repr(_eval_text[:200])}")

        violations = []
        has_hard_violation = False

        # --- 1. EVALUAR d_2 (Grafo: Lógica + Temporal unificados) ---
        d2, graph_violations = PropertyGraphEvaluator(active_graph, self.config).evaluate(
            eval_input,
            return_violations=True,
        )
        for v in graph_violations:
            if v["hardness"] == "hard":
                has_hard_violation = True
            violations.append(f"{v['id']}: {v['text']} ({v['hardness'].upper()})")

        # --- 2. EVALUAR d_3 (RAG Contexto Externo) ---
        d3, contradictory_contexts = _compute_d_3(
            eval_input,
            context_input,
            self.config,
            session_context.user_prompt,
            PropertyGraphEvaluator(active_graph, self.config),
        )
        for ctx in contradictory_contexts:
            violations.append(f"Contradicción RAG: {ctx}")

        # --- 3. EVALUAR d_1 (Deriva de Proyección) ---
        d1 = 0.0
        y_vector = None
        try:
            if isinstance(eval_input, (np.ndarray, list)) or hasattr(eval_input, "distribution"):
                m = np.asarray(getattr(eval_input, "distribution", eval_input), dtype=float)
                m = m / m.sum() if m.sum() > 1e-14 else np.ones_like(m) / m.size
                t = np.ones(m.size, dtype=float) / float(m.size)
                if session_context.v_hat and hasattr(session_context.v_hat, "semantic_vector"):
                    if len(session_context.v_hat.semantic_vector) == m.size:
                        t = np.asarray(session_context.v_hat.semantic_vector, dtype=float)
                d1 = _compute_d_1(m, t)
            else:
                y_vector = StringUtils.to_vector(
                    eval_input,
                    model_name=getattr(self.config, "semantic_embedding_model", "all-MiniLM-L6-v2"),
                )
                if active_graph:
                    y_vector = active_graph.project_to_manifold(y_vector)
                if session_context.v_hat and hasattr(session_context.v_hat, "semantic_vector"):
                    v_hat = np.asarray(session_context.v_hat.semantic_vector, dtype=float)
                    ny, nv = np.linalg.norm(y_vector), np.linalg.norm(v_hat)
                    y_vec_n = y_vector / ny if ny > 1e-12 else y_vector
                    v_hat_n = v_hat / nv if nv > 1e-12 else v_hat
                    d1 = float(np.clip(float(np.linalg.norm(y_vec_n - v_hat_n)) / 2.0, 0.0, 1.0))
        except Exception as ex:
            logger.warning(f"Error computing d_1: {ex}")

        # --- 4. CÁLCULO FINAL D_s (Matemática Pura Unificada) ---
        weights = getattr(
            self.config,
            "_normalized_weights",
            getattr(self.config, "dissonance_weights", [0.0, 0.33, 0.33, 0.33, 0.0, 0.0, 0.0]),
        )
        w1, w2, w3 = weights[1], weights[2], weights[3]

        # D_s = w1*d1 + w2*d2 + w3*d3
        d_s = w1 * d1 + w2 * d2 + w3 * d3
        if has_hard_violation:
            d_s = float("inf")

        raw_metrics = {
            "d_s": d_s,
            "has_hard_violation": has_hard_violation,
            "d_1": d1,
            "d_2": d2,
            "d_3": d3,
            "d_context": d3,
            "contradictory_contexts": contradictory_contexts,
            "violated_policies": violations,
            "y_vector": y_vector,
            "llm_output_text": _eval_text[:500],
        }
        return d_s, violations, raw_metrics

    def project_spsa(
        self,
        y_vec: np.ndarray,
        v_hat_vec: np.ndarray,
        const_metrics: Dict[str, Any],
        context_embs: List[np.ndarray] = None,
    ) -> Tuple[np.ndarray, float, List[Dict[str, Any]]]:
        import numpy as np

        if const_metrics.get("has_hard_violation", False):
            return y_vec, 1.0, [{"iteration": 0, "dissonance": 1.0, "backtracked": True}]

        z = np.copy(np.asarray(y_vec, dtype=float))
        if np.linalg.norm(z) > 1e-12:
            z /= np.linalg.norm(z)
        v_hat = np.asarray(v_hat_vec, dtype=float)
        if np.linalg.norm(v_hat) > 1e-12:
            v_hat /= np.linalg.norm(v_hat)

        weights = getattr(
            self.config,
            "_normalized_weights",
            getattr(self.config, "dissonance_weights", [0.0, 0.33, 0.33, 0.33, 0.0, 0.0, 0.0]),
        )
        w1, w2, w3 = weights[1], weights[2], weights[3]
        const_d2, const_d3 = const_metrics.get("d_2", 0.0), const_metrics.get("d_3", 0.0)

        def _cost(vec: np.ndarray) -> float:
            n = np.linalg.norm(vec)
            v = vec / n if n > 1e-12 else vec
            d1 = float(np.clip(float(np.linalg.norm(v - v_hat)) / 2.0, 0.0, 1.0))
            return w1 * d1 + w2 * const_d2 + w3 * const_d3

        best_z, best_loss = np.copy(z), _cost(z)
        history = [{"iteration": 0, "dissonance": float(best_loss), "backtracked": False}]

        green_zone = getattr(
            self.config, "diss_threshold_green", getattr(self.config, "allowed_epsilon", 0.10)
        )
        if best_loss <= green_zone:
            return best_z, best_loss, history

        a, c, iters = (
            getattr(self.config, "spsa_a", 0.1),
            getattr(self.config, "spsa_c", 0.05),
            getattr(self.config, "spsa_max_iters", 5),
        )

        for k in range(iters):
            delta = np.random.choice([-1.0, 1.0], size=z.size)
            grad = ((_cost(z + c * delta) - _cost(z - c * delta)) / (2.0 * c)) * delta
            z_next = z - a * grad
            if np.linalg.norm(z_next) > 1e-12:
                z_next /= np.linalg.norm(z_next)

            loss_next = _cost(z_next)
            history.append(
                {"iteration": k + 1, "dissonance": float(loss_next), "backtracked": False}
            )
            if loss_next < best_loss:
                best_loss, best_z = loss_next, np.copy(z_next)
            z = z_next
            if best_loss <= green_zone:
                break

        return best_z, best_loss, history
