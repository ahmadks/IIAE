from typing import Any, Set, Optional, Dict, List
from datetime import datetime, timezone
import math

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
        axiomas no-temporales activos en el grafo.
        """
        axioms = [ax for ax in self.graph.nodes.values() if ax.get("axiom_type") != "temporal"]
        if not axioms:
            return 0.0

        y_tokens = self._tokenize(self._to_str(y))
        y_vec = self._to_vec(y)  # None si y no es numérico

        total_weight = 0.0
        weighted_penalty = 0.0

        for ax in axioms:
            raw_penalty = self._logical_penalty(y_tokens, y_vec, ax)
            weight = self._axiom_weight(ax)
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
        axiomas con ``axiom_type == 'temporal'`` activos en el grafo.
        """
        temporal_axioms = [
            ax for ax in self.graph.nodes.values() if ax.get("axiom_type") == "temporal"
        ]
        if not temporal_axioms:
            return 0.0

        now = datetime.now(timezone.utc)

        total_weight = 0.0
        weighted_penalty = 0.0

        for ax in temporal_axioms:
            raw_penalty = self._temporal_penalty(ax, now)
            weight = self._axiom_weight(ax)
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
    def _axiom_text(axiom: Dict[str, Any]) -> str:
        parts = [
            str(axiom.get("source_text", "")),
            str(axiom.get("subject", "")),
            str(axiom.get("predicate", "")),
            str(axiom.get("object", "")),
        ]
        return " ".join(p for p in parts if p and p != "None")

    @staticmethod
    def _to_vec(y: Any) -> Optional[list]:
        try:
            import numpy as np
            candidate = getattr(y, "measure_vector", getattr(y, "distribution", y))
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

    def _logical_penalty(self, y_tokens: Set[str], y_vec: Optional[list], axiom: Dict[str, Any]) -> float:
        polarity = axiom.get("polarity", "affirmative")
        ax_embedding: Optional[list] = axiom.get("embedding")

        if ax_embedding is not None and y_vec is not None:
            dist = self._cosine_distance(y_vec, ax_embedding)
            similarity = 1.0 - dist
        else:
            ax_tokens = self._tokenize(self._axiom_text(axiom))
            if not ax_tokens:
                return 0.0
            similarity = self._jaccard(y_tokens, ax_tokens)

        if polarity == "affirmative":
            return 1.0 - similarity
        else:
            return similarity

    def _temporal_penalty(self, axiom: Dict[str, Any], now: datetime) -> float:
        valid_from = self._parse_dt(axiom.get("valid_from"))
        valid_until = self._parse_dt(axiom.get("valid_until"))

        if valid_until is None and axiom.get("ttl_seconds") is not None:
            base = valid_from or self._parse_dt(axiom.get("timestamp"))
            if base is not None:
                try:
                    ttl = float(axiom["ttl_seconds"])
                    from datetime import timedelta
                    valid_until = base + timedelta(seconds=ttl)
                except (ValueError, TypeError):
                    pass

        if valid_from is None and valid_until is None:
            return 0.0

        if valid_from is not None and now < valid_from:
            lag = (valid_from - now).total_seconds()
            if valid_until is not None:
                window = max(1.0, (valid_until - valid_from).total_seconds())
            else:
                window = 86400.0
            return min(1.0, lag / window)

        if valid_until is not None and now > valid_until:
            overrun = (now - valid_until).total_seconds()
            if valid_from is not None:
                window = max(1.0, (valid_until - valid_from).total_seconds())
            else:
                window = 86400.0
            return min(1.0, overrun / window)

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
    def _axiom_weight(axiom: Dict[str, Any]) -> float:
        priority = max(1, min(10, int(axiom.get("priority", 1))))
        hardness_mult = 2.0 if axiom.get("hardness") == "hard" else 1.0
        return (priority / 10.0) * hardness_mult
