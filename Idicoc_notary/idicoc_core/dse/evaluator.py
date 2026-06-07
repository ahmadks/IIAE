from __future__ import annotations
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import numpy as np
import torch
from transformers import LogitsProcessor

from idicoc_core.isg.graph_manager import PropertyGraph
from idicoc_core.api.schemas import SessionContext
from idicoc_core.utils.logger import get_logger
from idicoc_core.utils.string_utils import StringUtils
from idicoc_core.dse.metrics import (
    _cosine_distance,
    _compute_d_0,
    _compute_d_1,
    _compute_d_1_vectorized,
    _compute_d_2,
    _compute_d_3,
    _compute_d_4,
    _compute_d_5,
    _compute_d_6,
    _compute_context_contradiction,
)

logger = get_logger("dse.evaluator")


class DimensionalityMismatchError(ValueError):
    """Excepción para discordancia de dimensiones en cálculo de distancias."""

    pass


class PropertyGraphEvaluator:
    """
    Separates evaluation logic from the PropertyGraph data structure.
    Computes dissonance scores using deterministic logical/temporal evaluations.
    """

    def __init__(self, graph: PropertyGraph, config: Any = None):
        self.graph = graph
        self.config = config

    def evaluate(self, y: Any) -> float:
        """
        Evalúa la disonancia lógica de un estado candidato ``y`` contra los
        políticas no-temporales activos en el grafo.
        """
        policies = [ax for ax in self.graph.nodes.values() if ax.get("policy_type") != "temporal"]
        if not policies:
            return 0.0

        y_tokens = self._tokenize(self._to_str(y))
        y_vec = self._to_vec(y)

        total_weight = 0.0
        weighted_penalty = 0.0

        for ax in policies:
            if not self._policy_matches_mode(ax, y):
                continue

            raw_penalty = self._logical_penalty(y, y_tokens, y_vec, ax)
            hardness = ax.get("hardness", "hard")

            if hardness == "hard" and raw_penalty > 0:
                return float("inf")

            weight = self._policy_weight(ax, self.config)
            weighted_penalty += raw_penalty * weight
            total_weight += weight

        if total_weight == 0.0:
            return 0.0
        return min(1.0, weighted_penalty / total_weight)

    def get_violated_policies(self, y: Any) -> List[Dict[str, Any]]:
        violated = []
        policies = [ax for ax in self.graph.nodes.values() if ax.get("policy_type") != "temporal"]
        if not policies:
            return violated

        y_tokens = self._tokenize(self._to_str(y))
        y_vec = self._to_vec(y)

        for ax in policies:
            if not self._policy_matches_mode(ax, y):
                continue

            raw_penalty = self._logical_penalty(y, y_tokens, y_vec, ax)
            if raw_penalty > 0.0:
                violated.append(
                    {
                        "id": ax.get("id"),
                        "text": ax.get("text", ax.get("description", "")),
                        "hardness": ax.get("hardness", "hard"),
                        "penalty": raw_penalty,
                    }
                )
        return violated

    def compute_temporal(self, y: Any) -> float:
        temporal_policies = [
            ax for ax in self.graph.nodes.values() if ax.get("policy_type") == "temporal"
        ]
        if not temporal_policies:
            return 0.0

        now = datetime.now(timezone.utc)
        total_weight = 0.0
        weighted_penalty = 0.0

        for ax in temporal_policies:
            if not self._policy_matches_mode(ax, y):
                continue

            raw_penalty = self._temporal_penalty(ax, now)
            hardness = ax.get("hardness", "hard")

            if hardness == "hard" and raw_penalty > 0:
                return float("inf")

            weight = self._policy_weight(ax, self.config)
            weighted_penalty += raw_penalty * weight
            total_weight += weight

        if total_weight == 0.0:
            return 0.0
        return min(1.0, weighted_penalty / total_weight)

    compute_d_temporal = compute_temporal

    @staticmethod
    def _to_str(y: Any) -> str:
        if y is None:
            return ""
        if isinstance(y, str):
            return y
        try:
            import numpy as np

            if isinstance(y, np.ndarray):
                return str(y.tolist())
        except Exception:
            pass
        if isinstance(y, (list, tuple)):
            return str(list(y))
        if hasattr(y, "source_text"):
            return str(y.source_text)
        if hasattr(y, "data") and not hasattr(y, "shape"):
            return str(y.data)
        return str(y)

    @staticmethod
    def _input_mode(y: Any) -> str:
        if hasattr(y, "payload_type"):
            return str(getattr(y, "payload_type") or "all").lower()
        if isinstance(y, str):
            return "semantic"
        try:
            import numpy as np

            if isinstance(y, np.ndarray):
                return "numeric"
        except Exception:
            pass

        if isinstance(y, (list, tuple)):
            return "numeric"
        if hasattr(y, "distribution"):
            return getattr(y, "payload_type", "numeric")
        return "semantic"

    @staticmethod
    def _policy_mode(policy: Dict[str, Any]) -> str:
        return str(policy.get("mode", "all")).lower()

    def _policy_matches_mode(self, policy: Dict[str, Any], y: Any) -> bool:
        policy_mode = self._policy_mode(policy)
        if policy_mode == "all":
            return True
        input_mode = self._input_mode(y)
        if input_mode == "semantic":
            return policy_mode in ("semantic", "all")
        if input_mode == "numeric":
            return policy_mode in ("numeric", "all")
        return True

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        tokens = re.split(r"[\s,;:.!?()\[\]{}'\"]+", text.lower())
        return {t for t in tokens if t}

    @staticmethod
    def _policy_text(policy: Dict[str, Any]) -> str:
        parts = [
            str(policy.get("source_text", "")),
            str(policy.get("subject", "")),
            str(policy.get("predicate", "")),
            str(policy.get("object", "")),
        ]
        return " ".join(p for p in parts if p and p != "None")

    @staticmethod
    def _to_vec(y: Any) -> Optional[list]:
        try:
            import numpy as np

            candidate = getattr(y, "measure_vector", getattr(y, "distribution", y))
            if isinstance(candidate, str):
                nums = [float(m.group(0)) for m in re.finditer(r"[-+]?[0-9]*\.?[0-9]+", candidate)]
                if nums:
                    return nums
            arr = np.asarray(candidate, dtype=float)
            if arr.ndim == 1 and arr.size > 0:
                return arr.tolist()
        except Exception:
            pass
        return None

    def _cosine_distance(self, a: list, b: list) -> float:
        return _cosine_distance(a, b)

    def _evaluate_regex(self, ax: dict, y: Any) -> float:
        text_y = self._to_str(y)
        pattern = ax.get("pattern", ax.get("text", ""))

        if not pattern:
            return 0.0
        try:
            match = re.search(pattern, text_y, re.IGNORECASE)
        except re.error:
            match = re.search(pattern, text_y)

        polarity = ax.get("polarity", "affirmative")
        if polarity == "affirmative":
            return 0.0 if match else 1.0
        else:
            return 1.0 if match else 0.0

    def _logical_penalty(
        self, y: Any, y_tokens: Set[str], y_vec: Optional[list], policy: Dict[str, Any]
    ) -> float:
        a_type = policy.get("policy_type", "fact")
        polarity = policy.get("polarity", "affirmative")

        if a_type in ("regex", "numeric"):
            return self._evaluate_regex(policy, y)

        ax_embedding: Optional[list] = policy.get("embedding")
        if ax_embedding is None:
            from idicoc_core.utils.embedding_service import EmbeddingService

            try:
                ax_embedding = EmbeddingService().encode(self._policy_text(policy)).tolist()
                policy["embedding"] = ax_embedding
            except Exception as e:
                raise RuntimeError(
                    f"Failed to generate embedding for policy text: '{self._policy_text(policy)}' due to: {e}"
                ) from e

        if y_vec is None:
            from idicoc_core.utils.embedding_service import EmbeddingService

            try:
                y_text = self._to_str(y)
                y_vec = EmbeddingService().encode(y_text).tolist()
            except Exception as e:
                raise RuntimeError(
                    f"Failed to generate embedding for input text: '{y_text}' due to: {e}"
                ) from e
        elif ax_embedding is not None and len(y_vec) != len(ax_embedding):
            from idicoc_core.utils.embedding_service import EmbeddingService

            try:
                y_text = self._to_str(y)
                y_vec = EmbeddingService().encode(y_text).tolist()
            except Exception as e:
                raise RuntimeError(
                    f"Failed to generate embedding for input text: '{self._to_str(y)}' due to: {e}"
                ) from e

        dist = self._cosine_distance(y_vec, ax_embedding)
        similarity = 1.0 - dist

        if polarity == "affirmative":
            return 1.0 - similarity
        else:
            return similarity

    def _temporal_penalty(self, policy: Dict[str, Any], now: datetime) -> float:
        valid_from = self._parse_dt(policy.get("valid_from"))
        valid_until = self._parse_dt(policy.get("valid_until"))
        ttl_val = None

        if valid_until is None and policy.get("ttl_seconds") is not None:
            base = valid_from or self._parse_dt(policy.get("timestamp"))
            if base is not None:
                try:
                    ttl_val = float(policy["ttl_seconds"])
                    from datetime import timedelta

                    valid_until = base + timedelta(seconds=ttl_val)
                except (ValueError, TypeError):
                    pass

        if valid_from is None and valid_until is None:
            return 0.0

        if ttl_val is not None:
            window = max(1.0, ttl_val)
        elif valid_until is not None and valid_from is not None:
            window = max(1.0, (valid_until - valid_from).total_seconds())
        else:
            window = 86400.0

        if valid_from is not None and now < valid_from:
            lag = (valid_from - now).total_seconds()
            return 2.0 / (1.0 + math.exp(-lag / window)) - 1.0

        if valid_until is not None and now > valid_until:
            overrun = (now - valid_until).total_seconds()
            return 2.0 / (1.0 + math.exp(-overrun / window)) - 1.0

        return 0.0

    @staticmethod
    def _parse_dt(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        if isinstance(value, str):
            try:
                dt = datetime.fromisoformat(value)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    @staticmethod
    def _policy_weight(policy: Dict[str, Any], config: Any = None) -> float:
        priority = max(1, min(10, int(policy.get("priority", 1))))
        hard_mult = float(getattr(config, "policy_hard_weight_multiplier", 2.0))
        hardness_mult = hard_mult if policy.get("hardness") == "hard" else 1.0
        return (priority / 10.0) * hardness_mult


@dataclass(frozen=True)
class DissonanceEvaluationResult:
    structural_dissonance_ds: float
    factual_dissonance_df: float
    corrected_output: Any
    correction_applied: bool
    metrics: Dict[str, Any]

    def __iter__(self):
        yield self.structural_dissonance_ds
        yield self.factual_dissonance_df
        yield self.corrected_output
        yield self.correction_applied
        yield self.metrics


class DissonanceStrategy:
    def __init__(self, config: Any) -> None:
        self.config = config


class StructuralDissonanceStrategy(DissonanceStrategy):
    def __init__(
        self,
        config: Any,
        property_graph: Optional[PropertyGraph] = None,
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
        self._graph: Optional[PropertyGraph] = property_graph

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
            self.lambda_1 = 1.0
        elif abs(sum_lambda - 1.0) > 1e-5:
            self.lambda_0 /= sum_lambda
            self.lambda_1 /= sum_lambda
            self.lambda_2 /= sum_lambda
            self.lambda_3 /= sum_lambda
            self.lambda_4 /= sum_lambda
            self.lambda_5 /= sum_lambda
            self.lambda_6 /= sum_lambda

    def set_graph(self, graph: PropertyGraph) -> None:
        self._graph = graph

    def _validate_input(self, audit_input: Any, expected_size: int) -> np.ndarray:
        try:
            measure = np.asarray(getattr(audit_input, "distribution", audit_input), dtype=float)
        except (ValueError, TypeError):
            raise TypeError("El input no es una señal numérica válida.")
        if expected_size and expected_size > 0:
            if measure.size != expected_size:
                if measure.size < expected_size:
                    padded = np.zeros(expected_size, dtype=float)
                    padded[: measure.size] = measure
                    measure = padded
                else:
                    measure = measure[:expected_size]
        return measure

    def compute(
        self,
        audit_input: Any,
        context_input: List[str],
        context_policies: List[str],
        epsilon: float = 0.0,
        validate_conflicts: bool = False,
    ) -> DissonanceEvaluationResult:
        _ = validate_conflicts
        mu_raw = self._validate_input(audit_input, 4)
        total = mu_raw.sum()
        mu = mu_raw / total if total > 1e-14 else np.ones_like(mu_raw) / mu_raw.size

        s0_str = getattr(audit_input, "text_content", "")
        d0 = _compute_d_0(s0_str, "")

        n_ref = mu.size
        if n_ref > 0:
            # Para entradas de distribución/numéricas, el estado canónico (ancla canónica uniforme)
            # es la distribución uniforme. No se debe calcular usando el embedding de texto de la unicidad,
            # ya que la dimensionalidad y semántica son incompatibles.
            target_state = np.ones(n_ref, dtype=float) / float(n_ref)
            d1 = _compute_d_1(mu, target_state)
        else:
            d1 = 0.0

        d2 = 0.0
        if self._graph is not None:
            try:
                evaluator = PropertyGraphEvaluator(self._graph, self.config)
                d2 = float(evaluator.evaluate(audit_input))
            except Exception:
                pass

        d3 = 0.0
        if self._graph is not None:
            try:
                evaluator = PropertyGraphEvaluator(self._graph, self.config)
                d3 = float(evaluator.compute_temporal(audit_input))
            except Exception:
                pass

        d4 = 0.0
        d5 = 0.0
        d6 = 0.0

        evaluator_instance = None
        if self._graph is not None:
            evaluator_instance = PropertyGraphEvaluator(self._graph, self.config)

        d_context, contradictory_contexts = _compute_context_contradiction(
            audit_input, context_input, self.config, evaluator=evaluator_instance
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

        return DissonanceEvaluationResult(
            structural_dissonance_ds=d_s,
            factual_dissonance_df=d_context,
            corrected_output=audit_input,
            correction_applied=not is_compliant,
            metrics=metrics,
        )

    def compute_dissonance(
        self, y: Any, V_hat: Any, G_t: Any, context_input: list | None = None
    ) -> float:
        from idicoc_core.config import DEFAULT_SEMANTIC_EMBEDDING_MODEL

        model_name = getattr(
            self.config,
            "semantic_embedding_model",
            DEFAULT_SEMANTIC_EMBEDDING_MODEL,
        )
        y_vec = StringUtils.to_vector(y, model_name=model_name)
        v_hat_vec = StringUtils.to_vector(V_hat, model_name=model_name)

        d1 = _compute_d_1_vectorized(y_vec, v_hat_vec)

        d2 = 0.0
        d3 = 0.0
        if G_t is not None:
            evaluator = PropertyGraphEvaluator(G_t, self.config)
            d2 = float(evaluator.evaluate(y))
            d3 = float(evaluator.compute_temporal(y))

        if d2 == float("inf") or d3 == float("inf"):
            d_s = float("inf")
        else:
            d_s = max(0.0, min(1.0, self.lambda_1 * d1 + self.lambda_2 * d2 + self.lambda_3 * d3))

        d_context = 0.0
        if context_input:
            evaluator_instance = (
                PropertyGraphEvaluator(G_t, self.config) if G_t is not None else None
            )
            d_context, _ = _compute_context_contradiction(
                y, context_input, self.config, evaluator=evaluator_instance
            )

        return max(d_s, d_context)

    def select_canonical_input(self, canonical_state: Any) -> np.ndarray:
        return canonical_state.measure_vector

    def canonical_axis(self) -> str:
        return "measure"


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
        self.cuda_device = cuda_device or device

        if forbidden_token_ids is None:
            if w_bank is not None:
                if hard_only:
                    self.forbidden_token_ids = {
                        token_id for token_id, (hardness, _) in w_bank.items() if hardness == "hard"
                    }
                else:
                    self.forbidden_token_ids = set(w_bank.keys())
            else:
                self.forbidden_token_ids = set()
        else:
            self.forbidden_token_ids = set(forbidden_token_ids)

        device_to_use = cuda_device or device
        self.mask_tensor = torch.tensor(
            list(self.forbidden_token_ids), device=device_to_use, dtype=torch.long
        )

        self.intercepts_log: list[Dict] = [] if audit_trace else None
        self.intercepts_count = 0
        self.logits_processed_count = 0

    def __call__(
        self,
        _input_ids: torch.LongTensor,
        scores: torch.FloatTensor,
    ) -> torch.FloatTensor:
        self.logits_processed_count += 1
        if self.mask_tensor.numel() > 0:
            if self.mask_tensor.device != scores.device:
                raise RuntimeError(
                    f"Device mismatch between MUX mask ({self.mask_tensor.device}) and logits ({scores.device})."
                )
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

    def process_logits(
        self,
        logits: np.ndarray | torch.Tensor,
        _input_ids: Any = None,
    ) -> Any:
        is_numpy = isinstance(logits, np.ndarray)
        if is_numpy:
            scores = torch.tensor(logits, dtype=torch.float32)
        else:
            scores = logits

        was_1d = False
        if scores.dim() == 1:
            scores = scores.unsqueeze(0)
            was_1d = True

        scores = self.__call__(None, scores)

        if was_1d:
            scores = scores[0]

        if is_numpy:
            return scores.detach().cpu().numpy()
        return scores


class DissonanceStateEvaluator:
    """
    dse/evaluator.py
    Evaluates LLM output against active graph policies and RAG context.
    """

    def __init__(self, config: Any):
        self.config = config
        self.strategy = StructuralDissonanceStrategy(config=config)

    def evaluate(
        self, llm_output: str, session_context: SessionContext, active_graph: PropertyGraph
    ) -> Tuple[float, List[str], Dict[str, Any]]:
        """
        Evaluates dissonance and collects list of violated policy IDs/descriptions.
        Returns (d_s, list_of_violations, raw_metrics).
        """
        self.strategy.set_graph(active_graph)

        # Build list of contexts from RAG context
        context_input = []
        if session_context.rag_context:
            context_input = [
                ctx.strip() for ctx in session_context.rag_context.split("\n") if ctx.strip()
            ]

        # In case the input is numeric/distribution (e.g. from logic service tests),
        # parse it appropriately.
        eval_input: Any = llm_output
        try:
            # Check if llm_output is actually a list or array encoded as string
            if isinstance(llm_output, str) and (
                llm_output.startswith("[") or "array" in llm_output
            ):
                # Import ast safely to evaluate literal lists
                import ast

                parsed = ast.literal_eval(llm_output)
                if isinstance(parsed, (list, tuple)):
                    eval_input = np.array(parsed, dtype=float)
        except Exception:
            pass

        # Evaluate logic disonancia using PropertyGraphEvaluator
        evaluator = PropertyGraphEvaluator(active_graph, self.config)
        violations = []
        try:
            violated_nodes = evaluator.get_violated_policies(eval_input)
            for vn in violated_nodes:
                violations.append(f"{vn['id']}: {vn['text']} ({vn['hardness'].upper()})")
        except Exception as ex:
            logger.warning(f"Error computing logical violations: {ex}")

        # Compute d_logic, d_temporal, and d_context
        d_logic = evaluator.evaluate(eval_input)
        d_temporal = evaluator.compute_temporal(eval_input)

        # Semantic/RAG contradiction
        d_context, contradictory_contexts = _compute_context_contradiction(
            eval_input, context_input, self.config, session_context.user_prompt, evaluator
        )

        for ctx_text in contradictory_contexts:
            violations.append(f"Contradicción RAG: {ctx_text} (SOFT)")

        # ── D_s: Normalized weights from config ──────────────────────────────────
        weights = self.config._normalized_weights

        # ── d_1: stage 1 - Divergencia de Proyección ─────────────────────────────
        # Mide cuánto se alejó el LLM del estado canónico V_hat generado por el ISG.
        d1 = 0.0
        try:
            if (
                isinstance(eval_input, np.ndarray)
                or hasattr(eval_input, "distribution")
                or isinstance(eval_input, list)
            ):
                # Numeric/distribution input: compute KL-divergence to canonical state
                mu_raw = self.strategy._validate_input(eval_input, 4)
                total = mu_raw.sum()
                mu = mu_raw / total if total > 1e-14 else np.ones_like(mu_raw) / mu_raw.size
                n_ref = mu.size

                # Para entradas de distribución/numéricas, el estado canónico (ancla canónica uniforme)
                # es la distribución uniforme o el vector de V_hat si es compatible.
                if session_context.v_hat is not None and hasattr(session_context.v_hat, "semantic_vector"):
                    target_state = session_context.v_hat.semantic_vector
                    if not isinstance(target_state, np.ndarray):
                        target_state = np.asarray(target_state, dtype=float)
                    if target_state.size != n_ref:
                        target_state = np.ones(n_ref, dtype=float) / float(n_ref)
                else:
                    target_state = np.ones(n_ref, dtype=float) / float(n_ref)
                d1 = _compute_d_1(mu, target_state)
            else:
                # Text input: compute Projection Divergence against CanonicalState V_hat
                if session_context.v_hat is not None and hasattr(session_context.v_hat, "semantic_vector"):
                    from idicoc_core.config import DEFAULT_SEMANTIC_EMBEDDING_MODEL
                    model_name = getattr(
                        self.config,
                        "semantic_embedding_model",
                        DEFAULT_SEMANTIC_EMBEDDING_MODEL,
                    )
                    y_vector_raw = StringUtils.to_vector(eval_input, model_name=model_name)
                    if active_graph is not None:
                        y_vector = active_graph.project_to_manifold(y_vector_raw)
                    else:
                        y_vector = y_vector_raw

                    v_hat_vector = session_context.v_hat.semantic_vector
                    if not isinstance(v_hat_vector, np.ndarray):
                        v_hat_vector = np.asarray(v_hat_vector, dtype=float)

                    norm_y = np.linalg.norm(y_vector)
                    if norm_y > 1e-12:
                        y_vector = y_vector / norm_y
                    norm_v = np.linalg.norm(v_hat_vector)
                    if norm_v > 1e-12:
                        v_hat_vector = v_hat_vector / norm_v

                    # Kantorovich metric simplified to normalized L2 distance (simplified Wasserstein)
                    distancia = float(np.linalg.norm(y_vector - v_hat_vector))
                    d1 = float(np.clip(distancia / 2.0, 0.0, 1.0))
        except Exception as ex:
            logger.warning(f"Error computing d_1 (uniqueness/projection distance): {ex}")

        # ── D_s: Weighted Coalgebraic Dissonance ─────────────────────────────────
        # Dimensiones activas para texto:
        #   d_2 = violaciones del grafo de políticas    (λ_2)
        #   d_3 = restricciones temporales              (λ_3)
        #   d_context = disonancia de fase RAG→LLM      (λ_context)
        #
        # d_context tiene su propio coeficiente porque es la dimensión del
        # Middleware de Integridad: mide si el LLM alucina respecto al RAG.
        # Si d_2=inf (violación HARD), D_s=inf independientemente del resto.
        lambda_context = float(getattr(self.config, "lambda_context", 0.4))

        if d_logic == float("inf") or d_temporal == float("inf"):
            d_s = float("inf")
        else:
            if active_graph is not None:
                if hasattr(active_graph, "nodes") and isinstance(active_graph.nodes, dict):
                    has_logic_policies = any(
                        ax.get("policy_type") != "temporal" for ax in active_graph.nodes.values()
                    )
                    has_temporal_policies = any(
                        ax.get("policy_type") == "temporal" for ax in active_graph.nodes.values()
                    )
                else:
                    has_logic_policies = True
                    has_temporal_policies = True
            else:
                has_logic_policies = False
                has_temporal_policies = False

            policy_dissonance = weights[1] * d1 + weights[2] * d_logic + weights[3] * d_temporal

            # Integrar d_context como término ponderado + floor de seguridad
            # D_s = (1 - λ_context) * D_policy + λ_context * d_context
            # El max() garantiza que una contradicción RAG severa siempre escale D_s
            weighted_context = lambda_context * d_context
            d_s = (1.0 - lambda_context) * policy_dissonance + weighted_context
            d_s = max(d_s, d_context * lambda_context)  # floor proporcional

        # Raw metrics breakdown
        raw_metrics = {
            "d_s": d_s,
            "d_0": 0.0,
            "d_1": d1,
            "d_2": d_logic,
            "d_3": d_temporal,
            "d_4": 0.0,
            "d_5": 0.0,
            "d_6": 0.0,
            "d_context": d_context,
            "lambda_context": lambda_context,
            "effective_threshold": self.config.allowed_epsilon,
            "contradictory_contexts": contradictory_contexts,
            "violated_policies": violations,
            "d_logic": d_logic,
            "d_temporal": d_temporal,
        }

        return d_s, violations, raw_metrics


class AuditEntropyModule:
    """Modulo de Entropía de Auditoría (AEM) para el conteo de señales y registro de auditorías."""

    def __init__(self) -> None:
        self.total_signals: int = 0
        self.valid_signals: int = 0
        self.rejected_signals: int = 0
        self.audit_trail_map: List[Dict[str, Any]] = []

    def record_admission(self, metadata: Dict[str, Any] | None = None) -> None:
        self.total_signals += 1
        self.valid_signals += 1

    def record_admission_from_correction(self, metadata: Dict[str, Any] | None = None) -> None:
        self.total_signals += 1
        self.valid_signals += 1

    def record_rejection(self, metadata: Dict[str, Any]) -> None:
        self.total_signals += 1
        self.rejected_signals += 1
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), **(metadata or {})}
        self.audit_trail_map.append(record)

    def get_counters(self) -> Tuple[int, int, int]:
        return self.total_signals, self.valid_signals, self.rejected_signals

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        return self.audit_trail_map
