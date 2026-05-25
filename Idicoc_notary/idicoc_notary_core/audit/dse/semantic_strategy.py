from __future__ import annotations
from typing import Any, Dict, List, Tuple, TYPE_CHECKING

from .dissonance_strategy import DissonanceStrategy

# Inicialización diferida de librerías
SentenceTransformer = None
AutoModelForSequenceClassification = None
AutoTokenizer = None

if TYPE_CHECKING:
    from idicoc_notary_core.audit.config import AuditConfig
    from idicoc_notary_core.kernel.source.anchor import SourceAnchor
    import numpy as np


class SemanticDissonanceStrategy(DissonanceStrategy):
    def __init__(self, config: "AuditConfig") -> None:
        super().__init__(config)

        global SentenceTransformer, AutoModelForSequenceClassification, AutoTokenizer
        if SentenceTransformer is None:
            from sentence_transformers import SentenceTransformer
        if AutoTokenizer is None or AutoModelForSequenceClassification is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

        import numpy as np
        import torch

        self.np = np
        self.torch = torch
        self.encoder = SentenceTransformer(config.semantic_embedding_model)
        self.nli_tokenizer = AutoTokenizer.from_pretrained(config.semantic_nli_model)
        self.nli_model = AutoModelForSequenceClassification.from_pretrained(config.semantic_nli_model)

        self.contradiction_idx = None
        if hasattr(self.nli_model.config, 'id2label'):
            for idx, label in self.nli_model.config.id2label.items():
                if str(label).lower() == 'contradiction':
                    self.contradiction_idx = int(idx)
                    break

        if self.contradiction_idx is None:
            self.contradiction_idx = getattr(self.config, 'nli_contradiction_index', 0)

        self._nli_cache: Dict[Tuple[str, str], float] = {}

    def _cosine_distance(self, a: "np.ndarray", b: "np.ndarray") -> float:
        dot_product = self.np.dot(a, b)
        norm_a = self.np.linalg.norm(a)
        norm_b = self.np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0
        return float(self.np.clip(1.0 - (dot_product / (norm_a * norm_b)), 0.0, 1.0))

    def _nli_contradiction(self, premise: str, hypothesis: str) -> float:
        key = (premise, hypothesis)
        if key in self._nli_cache:
            return self._nli_cache[key]

        inputs = self.nli_tokenizer(premise, hypothesis, return_tensors='pt', truncation=True)
        with self.torch.no_grad():
            outputs = self.nli_model(**inputs)

        probs = self.torch.softmax(outputs.logits, dim=-1).squeeze().tolist()
        if isinstance(probs, float):
            return probs

        score = float(probs[self.contradiction_idx])
        self._nli_cache[key] = score
        return score

    def _combined_distance(self, source_emb: "np.ndarray", ref_emb: "np.ndarray", premise: str, hypothesis: str) -> float:
        cos_dist = self._cosine_distance(source_emb, ref_emb)
        nli_contra = self._nli_contradiction(premise, hypothesis)
        return max(cos_dist, nli_contra)

    def compute(
        self,
        audit_input: Any,
        context_input: List[str],
        context_axioms: List[str],
        source_anchor: "SourceAnchor",
        epsilon: float = 0.0,
        validate_conflicts: bool = False,
    ) -> Tuple[float, float, Any, bool, Dict[str, Any]]:
        semantic_input = str(audit_input) if audit_input is not None else ""
        if not semantic_input.strip():
            return 1.0, 1.0, '[REJECT] Salida vacía o colapso de señal.', True, {
                'error': 'empty_output'
            }

        normalize = getattr(self.config, 'embedding_normalize', True)
        source_embedding = self.encoder.encode(semantic_input, normalize_embeddings=normalize)

        # -----------------------------------------------------------------
        # EVALUACIÓN DE LA COÁLGEBRA TERMINAL (SourceAnchor)
        # -----------------------------------------------------------------
        anchor_identity = source_anchor.identity

        if isinstance(anchor_identity, str):
            anchor_embedding = self.encoder.encode(anchor_identity, normalize_embeddings=normalize)
            d_terminal = self._combined_distance(source_embedding, anchor_embedding, anchor_identity, semantic_input)
        else:
            anchor_embedding = anchor_identity
            d_terminal = self._cosine_distance(source_embedding, anchor_embedding)

        rigidity_threshold = getattr(self.config, 'terminal_rigidity_threshold', 0.01)
        terminality_violation = d_terminal > (rigidity_threshold + epsilon)

        max_axiom_distance = 0.0
        max_context_distance = 0.0
        violated_axioms: list[str] = []
        contradictory_contexts: list[str] = []
        support_found = False

        axiom_embs: Dict[str, "np.ndarray"] = {}
        context_embs: Dict[str, "np.ndarray"] = {}

        for axiom in context_axioms:
            ax_embedding = self.encoder.encode(axiom, normalize_embeddings=normalize)
            axiom_embs[axiom] = ax_embedding

            distance = self._combined_distance(source_embedding, ax_embedding, axiom, semantic_input)
            max_axiom_distance = max(max_axiom_distance, distance)
            if distance > self.config.context_axiom_conflict_threshold:
                violated_axioms.append(axiom)

        for chunk in context_input:
            chunk_embedding = self.encoder.encode(chunk, normalize_embeddings=normalize)
            context_embs[chunk] = chunk_embedding

            distance = self._combined_distance(source_embedding, chunk_embedding, chunk, semantic_input)
            max_context_distance = max(max_context_distance, distance)
            if distance > self.config.contradiction_snapping_threshold:
                contradictory_contexts.append(chunk)
            if distance <= self.config.correction_base_tolerance:
                support_found = True

        d_logic = max(max_axiom_distance, max_context_distance, d_terminal)
        D_s = float(self.np.clip(d_logic, 0.0, 1.0))
        D_f = max_context_distance if context_input else 0.0

        allowable_threshold = self.config.correction_base_tolerance + epsilon
        snapping_flag = (not support_found) and (max_context_distance > self.config.contradiction_snapping_threshold)
        correction_flag = (D_s > allowable_threshold) or snapping_flag or terminality_violation

        corrected_output: Any = semantic_input
        if correction_flag:
            if terminality_violation:
                corrected_output = (
                    f"[STRUCTURAL CORRUPTION] Violación de la Coálgebra Terminal. "
                    f"Desfase del origen detectable (d_terminal = {d_terminal:.4f}). Isomorfismo F_k roto."
                )
            elif snapping_flag:
                corrected_output = (
                    f"[SNAPPING ACTIVE] Disonancia factual insostenible (D_f = {D_f:.4f}). "
                    f"Estado revertido al contexto canónico primario: "
                    f"'{context_input[0] if context_input else 'Sin soporte factual disponible'}'"
                )
            else:
                corrected_output = (
                    f"[CRITICAL REJECTION] Disonancia estructural fuera de la frontera permitida "
                    f"(D_s = {D_s:.4f}, Máx Tolerancia = {allowable_threshold:.4f})."
                )

        metrics = {
            'd_s': D_s,
            'd_logic': d_logic,
            'd_factual': D_f,
            'd_terminal': d_terminal,
            'terminality_violation': terminality_violation,
            'max_axiom_distance': max_axiom_distance,
            'max_context_distance': max_context_distance,
            'violated_axioms': violated_axioms,
            'contradictory_contexts': contradictory_contexts,
            'support_found': support_found,
            'reference_count': len(context_axioms) + len(context_input) + 1,
            'snapping_flag': snapping_flag,
            'correction_flag': correction_flag,
        }

        if validate_conflicts and context_input and context_axioms:
            metrics['context_axiom_conflicts'] = self._check_context_axiom_conflicts(
                context_input,
                context_axioms,
                context_embs,
                axiom_embs,
                threshold=self.config.context_axiom_conflict_threshold,
            )
        else:
            metrics['context_axiom_conflicts'] = []

        return D_s, D_f, corrected_output, correction_flag, metrics
