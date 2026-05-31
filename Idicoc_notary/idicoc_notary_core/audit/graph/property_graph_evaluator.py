from typing import Any, Set, Optional, Dict, List
from datetime import datetime, timezone
import math
import re

from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph

class PropertyGraphEvaluator:
    """
    Separates evaluation logic from the PropertyGraph data structure.
    Computes dissonance scores using deterministic logical/temporal evaluations.
    """

    def __init__(self, graph: PropertyGraph):
        self.graph = graph


    # ──────────────────────────────────────────────────────────────────────────
    # evaluate(y) — dissonancia lógica
    # ──────────────────────────────────────────────────────────────────────────

    def evaluate(self, y: Any) -> float:
        """
        Evalúa la disonancia lógica de un estado candidato ``y`` contra los
        politicas no-temporales activos en el grafo.
        """
        policies = [ax for ax in self.graph.nodes.values() if ax.get("policy_type") != "temporal"]
        if not policies:
            return 0.0

        y_tokens = self._tokenize(self._to_str(y))
        y_vec = self._to_vec(y)  # None si y no es numérico

        total_weight = 0.0
        weighted_penalty = 0.0

        for ax in policies:
            raw_penalty = self._logical_penalty(y_tokens, y_vec, ax)
            hardness = ax.get("hardness", "hard")  # Default is hard
            
            if hardness == "hard" and raw_penalty > 0:
                # Violación de Hard Invariant (C_hard): rechazo incondicional
                return float('inf')
                
            weight = self._policy_weight(ax)
            weighted_penalty += raw_penalty * weight
            total_weight += weight

        if total_weight == 0.0:
            return 0.0
        return min(1.0, weighted_penalty / total_weight)

    # ──────────────────────────────────────────────────────────────────────────
    # compute_temporal(y) — dissonancia temporal
    # ──────────────────────────────────────────────────────────────────────────

    def compute_temporal(self, y: Any) -> float:
        """
        Evalúa la disonancia temporal del estado candidato ``y`` contra los
        politicas con ``policy_type == 'temporal'`` activos en el grafo.
        """
        temporal_policies = [
            ax for ax in self.graph.nodes.values() if ax.get("policy_type") == "temporal"
        ]
        if not temporal_policies:
            return 0.0

        now = datetime.now(timezone.utc)

        total_weight = 0.0
        weighted_penalty = 0.0

        for ax in temporal_policies:
            raw_penalty = self._temporal_penalty(ax, now)
            hardness = ax.get("hardness", "hard")
            
            if hardness == "hard" and raw_penalty > 0:
                return float('inf')
                
            weight = self._policy_weight(ax)
            weighted_penalty += raw_penalty * weight
            total_weight += weight

        if total_weight == 0.0:
            return 0.0
        return min(1.0, weighted_penalty / total_weight)

    compute_d_temporal = compute_temporal

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers internos (migrados desde PropertyGraph)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _to_str(y: Any) -> str:
        if y is None:
            return ""
        if isinstance(y, str):
            return y
        if hasattr(y, "data"):
            return str(y.data)
        if hasattr(y, "source_text"):
            return str(y.source_text)
        return str(y)

    @staticmethod
    def _tokenize(text: str) -> Set[str]:
        import re
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
            import re
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

    @staticmethod
    def _cosine_distance(a: list, b: list) -> float:
        if len(a) != len(b):
            n = max(len(a), len(b))
            a = a + [0.0] * (n - len(a))
            b = b + [0.0] * (n - len(b))
        dot = sum(x * z for x, z in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a < 1e-12 or norm_b < 1e-12:
            return 1.0
        cosine_sim = dot / (norm_a * norm_b)
        return 1.0 - max(-1.0, min(1.0, cosine_sim))

    @staticmethod
    def _jaccard(set_a: Set[str], set_b: Set[str]) -> float:
        if not set_a and not set_b:
            return 1.0
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        return intersection / union if union > 0 else 0.0


    def _evaluate_regex(self, ax: dict, y_tokens: Set[str]) -> float:
        """Evaluate regex policies on string representations."""
        import re
        text_y = " ".join(y_tokens)
        pattern = ax.get("pattern", ax.get("text", ""))
        
        if not pattern:
            return 0.0
            
        match = re.search(pattern, text_y)
        
        polarity = ax.get("polarity", "affirmative")
        if polarity == "affirmative":
            return 0.0 if match else 1.0
        else:
            return 1.0 if match else 0.0

    def _logical_penalty(self, y_tokens: Set[str], y_vec: Optional[list], policy: Dict[str, Any]) -> float:
        """
        Evaluate logical constraints (policies) against output y.
        Policies are evaluated based on their 'policy_type'.
        """
        a_type = policy.get("policy_type", "fact")
        polarity = policy.get("polarity", "affirmative")
        
        if a_type == "regex":
            return self._evaluate_regex(policy, y_tokens)
        else:
            # Semantic / default evaluation
            ax_embedding: Optional[list] = policy.get("embedding")
            if ax_embedding is not None and y_vec is not None:
                dist = self._cosine_distance(y_vec, ax_embedding)
                similarity = 1.0 - dist
            else:
                ax_tokens = self._tokenize(self._policy_text(policy))
                if not ax_tokens:
                    return 0.0
                similarity = self._jaccard(y_tokens, ax_tokens)

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

        # Definir la ventana de validez para el suavizado de la penalización
        if ttl_val is not None:
            # Si es una restricción por TTL, usamos el propio TTL como ventana
            window = max(1.0, ttl_val)
        elif valid_until is not None and valid_from is not None:
            # Si hay ventana explícita, usamos su duración
            window = max(1.0, (valid_until - valid_from).total_seconds())
        else:
            # Por defecto, 1 día
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
    def _policy_weight(policy: Dict[str, Any]) -> float:
        priority = max(1, min(10, int(policy.get("priority", 1))))
        hardness_mult = 2.0 if policy.get("hardness") == "hard" else 1.0
        return (priority / 10.0) * hardness_mult
