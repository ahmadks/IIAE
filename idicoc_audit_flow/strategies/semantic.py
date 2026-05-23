from __future__ import annotations
from typing import Any, Dict, List, Tuple

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from .base import DissonanceStrategy


class SemanticDissonanceStrategy(DissonanceStrategy):
    def __init__(
        self,
        embedding_model_name: str,
        nli_model_name: str,
        delta_fp: float = 0.15,
    ) -> None:
        self.encoder = SentenceTransformer(embedding_model_name)
        self.nli_tokenizer = AutoTokenizer.from_pretrained(nli_model_name)
        self.nli_model = AutoModelForSequenceClassification.from_pretrained(nli_model_name)
        self.delta_fp = delta_fp

    def _cosine_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0
        return float(1.0 - (dot_product / (norm_a * norm_b)))

    def _nli_contradiction(self, premise: str, hypothesis: str) -> float:
        inputs = self.nli_tokenizer(premise, hypothesis, return_tensors='pt', truncation=True)
        with torch.no_grad():
            outputs = self.nli_model(**inputs)

        probs = torch.softmax(outputs.logits, dim=-1).squeeze().tolist()
        if isinstance(probs, float):
            return probs
        return float(probs[0])

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
            ctx_emb = self.encoder.encode(ctx, normalize_embeddings=True)
            for ax in context_axioms:
                ax_emb = self.encoder.encode(ax, normalize_embeddings=True)
                cosine_distance = self._cosine_distance(ctx_emb, ax_emb)
                contradiction_score = self._nli_contradiction(premise=ax, hypothesis=ctx)
                if max(cosine_distance, contradiction_score) > threshold:
                    conflicts.append({
                        "context_snippet": ctx[:100],
                        "axiom_snippet": ax[:100],
                        "cosine_distance": cosine_distance,
                        "nli_contradiction": contradiction_score,
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
        if not source_input.strip():
            return 1.0, 1.0, '[REJECT] Salida vacía o colapso de señal.', True, {
                'error': 'empty_output'
            }

        source_embedding = self.encoder.encode(source_input, normalize_embeddings=True)

        references: list[tuple[str, bool]] = [
            *( (axiom, True) for axiom in context_axioms ),
            *( (chunk, False) for chunk in context_input ),
        ]

        penalties: list[float] = []
        max_cosine = 0.0
        max_axiom_contradiction = 0.0
        max_context_contradiction = 0.0
        violated_axioms: list[str] = []
        contradictory_contexts: list[str] = []
        support_found = False

        for reference, is_axiom in references:
            ref_embedding = self.encoder.encode(reference, normalize_embeddings=True)
            cosine_distance = self._cosine_distance(source_embedding, ref_embedding)
            contradiction_score = self._nli_contradiction(premise=reference, hypothesis=source_input)

            weight = 1.5 if is_axiom else 1.0
            if is_axiom and 'hard' in reference.lower():
                weight = 2.0

            penalty = max(cosine_distance, contradiction_score) * weight
            penalties.append(min(penalty, 1.0))
            max_cosine = max(max_cosine, cosine_distance)

            if is_axiom:
                max_axiom_contradiction = max(max_axiom_contradiction, contradiction_score)
                if contradiction_score > 0.5:
                    violated_axioms.append(reference)
            else:
                max_context_contradiction = max(max_context_contradiction, contradiction_score)
                if contradiction_score > 0.5:
                    contradictory_contexts.append(reference)

            if not is_axiom and cosine_distance <= self.delta_fp:
                support_found = True

        D_s = 1.0 if not penalties else min(1.0, sum(penalties) / len(penalties))

        D_f = 1.0
        if context_input:
            factual_cosines = [
                self._cosine_distance(source_embedding, self.encoder.encode(chunk, normalize_embeddings=True))
                for chunk in context_input
            ]
            factual_contradictions = [
                self._nli_contradiction(premise=chunk, hypothesis=source_input)
                for chunk in context_input
            ]
            D_f = max(min(factual_cosines) if factual_cosines else 1.0, max(factual_contradictions) if factual_contradictions else 0.0)

        allowable_threshold = self.delta_fp + epsilon
        correction_flag = D_s > allowable_threshold
        corrected_output = source_input

        if correction_flag:
            corrected_output = (
                '[CRITICAL REJECTION] La salida incurre en disonancia con el grafo de referencia y los axiomas.'
            )

        metrics = {
            'reference_count': len(references),
            'average_penalty': D_s,
            'max_cosine_distance': max_cosine,
            'max_axiom_contradiction': max_axiom_contradiction,
            'max_context_contradiction': max_context_contradiction,
            'violated_axioms': violated_axioms,
            'contradictory_contexts': contradictory_contexts,
            'support_found': support_found,
            'context_input_count': len(context_input),
            'context_axiom_count': len(context_axioms),
            'factual_dissonance': D_f,
        }

        if validate_conflicts:
            metrics['context_axiom_conflicts'] = self._check_context_axiom_conflicts(
                context_input,
                context_axioms,
                threshold=self.delta_fp,
            )
        else:
            metrics['context_axiom_conflicts'] = []

        return D_s, D_f, corrected_output, correction_flag, metrics
