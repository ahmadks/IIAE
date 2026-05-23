from __future__ import annotations
import json
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from idicoc_utils.hashing import sha256_hex

from .base import DissonanceStrategy

if TYPE_CHECKING:
    from idicoc_audit_flow.config import AuditConfig


class MathematicalDissonanceStrategy(DissonanceStrategy):
    def __init__(
        self,
        config: AuditConfig,
        expected_hash: Optional[str] = None,
    ) -> None:
        self.config = config
        self.weights = config.mathematical_weights
        self.expected_hash = expected_hash
        self.embedder = None
        if config.mathematical_embedding_model:
            from sentence_transformers import SentenceTransformer
            self.embedder = SentenceTransformer(config.mathematical_embedding_model)

    @staticmethod
    def _similarity_ratio(a: str, b: str) -> float:
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a, b).ratio()

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text.strip().lower())

    @staticmethod
    def _token_freq(text: str) -> dict[str, int]:
        tokens = re.findall(r"\w+", text.lower())
        freq: dict[str, int] = {}
        for token in tokens:
            freq[token] = freq.get(token, 0) + 1
        return freq

    @staticmethod
    def _manhattan_distance(freq1: dict[str, int], freq2: dict[str, int]) -> float:
        all_keys = set(freq1) | set(freq2)
        distance = sum(abs(freq1.get(k, 0) - freq2.get(k, 0)) for k in all_keys)
        max_value = sum(freq1.values()) + sum(freq2.values())
        return distance / max(max_value, 1)

    @staticmethod
    def _hash_distance(value: str, expected: str) -> float:
        if not expected:
            return 0.0
        current_hash = sha256_hex(value)
        min_len = min(len(current_hash), len(expected))
        diff = sum(c1 != c2 for c1, c2 in zip(current_hash, expected[:min_len]))
        return diff / max(min_len, 1)

    @staticmethod
    def _is_json(text: str) -> bool:
        try:
            json.loads(text)
            return True
        except Exception:
            return False

    def _check_context_axiom_conflicts(
        self,
        context_input: List[str],
        context_axioms: List[str],
        threshold: float = 0.5,
    ) -> List[Dict[str, Any]]:
        conflicts: list[Dict[str, Any]] = []
        if not context_input or not context_axioms:
            return conflicts

        for ctx in context_input:
            for ax in context_axioms:
                if self.embedder:
                    ctx_emb = self.embedder.encode([ctx])[0]
                    ax_emb = self.embedder.encode([ax])[0]
                    distance = self._cosine_distance(ctx_emb, ax_emb)
                else:
                    similarity = self._similarity_ratio(ctx, ax)
                    distance = 1.0 - similarity

                if distance > threshold:
                    conflicts.append({
                        "context_snippet": ctx[:100],
                        "axiom_snippet": ax[:100],
                        "distance": distance,
                    })
        return conflicts

    def compute(
        self,
        source_input: str,
        context_input: List[str],
        context_axioms: List[str],
        epsilon: float = 0.0,
        validate_conflicts: bool = False,
    ) -> Tuple[float, float, str, bool, Dict[str, Any]]:
        normalized_source = self._normalize_text(source_input)

        d1 = 1.0 - self._similarity_ratio(source_input, normalized_source)

        reference = context_axioms + context_input
        if reference and self.embedder:
            source_emb = self.embedder.encode([source_input])[0]
            ref_embs = self.embedder.encode(reference)
            distances = [self._cosine_distance(source_emb, ref_emb) for ref_emb in ref_embs]
            d2 = min(distances)
        else:
            if reference:
                overlap = max(self._similarity_ratio(source_input, ref) for ref in reference)
                d2 = 1.0 - overlap
            else:
                d2 = 0.0

        d3 = 0.0
        if context_input and self.expected_hash:
            combined = "".join(context_input)
            d3 = self._hash_distance(combined, self.expected_hash)

        if context_input:
            source_freq = self._token_freq(source_input)
            context_freq = {}
            for chunk in context_input:
                chunk_freq = self._token_freq(chunk)
                for token, count in chunk_freq.items():
                    context_freq[token] = context_freq.get(token, 0) + count
            d4 = self._manhattan_distance(source_freq, context_freq)
        else:
            d4 = 0.0

        violated_axioms = []
        if context_axioms:
            normalized_axioms = [self._normalize_text(ax) for ax in context_axioms]
            for ax, norm_ax in zip(context_axioms, normalized_axioms):
                if norm_ax not in normalized_source:
                    violated_axioms.append(ax)
            d5 = 1.0 if violated_axioms else 0.0
        else:
            d5 = 0.0

        if context_input and self.embedder:
            source_emb = self.embedder.encode([source_input])[0]
            ref_embs = self.embedder.encode(context_input)
            distances = [self._euclidean_distance(source_emb, ref_emb) for ref_emb in ref_embs]
            d6 = min(distances)
        else:
            d6 = 0.0

        d7 = 0.0 if self._is_json(source_input) else 1.0

        stages = [d1, d2, d3, d4, d5, d6, d7]
        D_s = sum(w * d for w, d in zip(self.weights, stages))
        denominator = sum(self.weights[i] for i in (1, 3, 5)) or 1.0
        D_f = (
            self.weights[1] * d2
            + self.weights[3] * d4
            + self.weights[5] * d6
        ) / denominator

        allowable_threshold = self.config.correction_base_tolerance + epsilon
        correction_flag = D_s > allowable_threshold
        corrected_output = source_input
        if correction_flag:
            corrected_output = "[MATHEMATICAL DISSONANCE] Desviación estructural detectada."

        contradictory_contexts = []
        context_contradiction = 0.0
        if context_input:
            if self.embedder:
                source_emb = self.embedder.encode([source_input])[0]
                ref_embs = self.embedder.encode(context_input)
                distances = [self._cosine_distance(source_emb, ref_emb) for ref_emb in ref_embs]
                context_contradiction = max(distances) if distances else 0.0
                for ctx, dist in zip(context_input, distances):
                    if dist > self.config.semantic_contradiction_snapping_threshold:
                        contradictory_contexts.append(ctx)
            else:
                for ctx in context_input:
                    dist = 1.0 - self._similarity_ratio(source_input, ctx)
                    if dist > context_contradiction:
                        context_contradiction = dist
                    if dist > self.config.semantic_contradiction_snapping_threshold:
                        contradictory_contexts.append(ctx)

        metrics = {
            "stage_metrics": {f"d{i+1}": value for i, value in enumerate(stages)},
            "weighted_sum": D_s,
            # d_logic mirrors D_s in the mathematical mode: the weighted sum already acts as the
            # coalgebraic frontier measure over structural deviations (axiom violations, hash
            # distance, embedding distance). Exposed here so the pipeline can always find d_logic.
            "d_logic": D_s,
            "factual_dissonance": D_f,
            "context_contradiction": context_contradiction,
            "violated_axioms": violated_axioms,
            "contradictory_contexts": contradictory_contexts,
        }

        if validate_conflicts:
            metrics["context_axiom_conflicts"] = self._check_context_axiom_conflicts(
                context_input,
                context_axioms,
                threshold=self.config.context_axiom_conflict_threshold,
            )
        else:
            metrics["context_axiom_conflicts"] = []

        return D_s, D_f, corrected_output, correction_flag, metrics

    @staticmethod
    def _euclidean_distance(a: list[float], b: list[float]) -> float:
        return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5

    @staticmethod
    def _cosine_distance(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 1.0
        similarity = dot / (norm_a * norm_b)
        return 1.0 - max(min(similarity, 1.0), -1.0)
