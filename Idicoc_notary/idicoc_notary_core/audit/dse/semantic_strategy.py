from __future__ import annotations
from typing import Any, Dict, List, Tuple, TYPE_CHECKING
import hashlib
import numpy as np

from .dissonance_strategy import DissonanceStrategy
from idicoc_notary_core.kernel.source.anchor import SourceAnchor

# Repositorio compartido de juicios NLI
NLI_VERDICT_REGISTRY: dict[tuple[str, str], float] = {}

# Inicialización diferida de librerías pesadas
SentenceTransformer = None
AutoModelForSequenceClassification = None
AutoTokenizer = None

if TYPE_CHECKING:
    from idicoc_notary_core.audit.config import AuditConfig
    from idicoc_notary_core.kernel.projection.invariant_generator import CanonicalState


class SemanticDissonanceStrategy(DissonanceStrategy):
    def __init__(self, config: "AuditConfig") -> None:
        super().__init__(config)

        global SentenceTransformer, AutoModelForSequenceClassification, AutoTokenizer
        if SentenceTransformer is None:
            from sentence_transformers import SentenceTransformer
        if AutoTokenizer is None or AutoModelForSequenceClassification is None:
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

        import torch

        self.torch = torch
        self.encoder = SentenceTransformer(config.semantic_embedding_model)
        self.nli_tokenizer = AutoTokenizer.from_pretrained(config.semantic_nli_model)
        self.nli_model = AutoModelForSequenceClassification.from_pretrained(config.semantic_nli_model)

        self.contradiction_idx = self._resolve_contradiction_index()
        self._nli_cache = NLI_VERDICT_REGISTRY
        if not isinstance(self._nli_cache, dict):
            self._nli_cache = {}
        self._encoder_signature_valid, self._encoder_signature_actual = self._verify_encoder_signature()
        raw_k = getattr(self.config, 'constant_k', "canon_vacio")
        normalize = getattr(self.config, 'embedding_normalize', True)

        if isinstance(raw_k, str):
            if not raw_k.strip():
                raw_k = "canon_vacio"
            k_vector = self.encoder.encode(raw_k, normalize_embeddings=normalize)
            self._default_anchor = SourceAnchor(k_vector)
        elif isinstance(raw_k, np.ndarray):
            self._default_anchor = SourceAnchor(raw_k)
        else:
            k_vector = self.encoder.encode("canon_vacio", normalize_embeddings=normalize)
            self._default_anchor = SourceAnchor(k_vector)

    def _cosine_distance(self, a: np.ndarray, b: np.ndarray) -> float:
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0
        return float(np.clip(1.0 - (dot_product / (norm_a * norm_b)), 0.0, 1.0))

    def _nli_contradiction(self, premise: str, hypothesis: str) -> float:
        key = (premise, hypothesis)
        if key in self._nli_cache:
            return self._nli_cache[key]

        try:
            inputs = self.nli_tokenizer(premise, hypothesis, return_tensors='pt', truncation=True)
            with self.torch.no_grad():
                outputs = self.nli_model(**inputs)

            probs = self.torch.softmax(outputs.logits, dim=-1).squeeze().tolist()
            if isinstance(probs, float):
                score = float(probs)
            else:
                score = float(probs[self.contradiction_idx])
        except Exception:
            score = 0.0

        self._nli_cache[key] = score
        return score

    def _is_nli_warning(self, geom_dist: float, nli_score: float) -> bool:
        warning_threshold = getattr(self.config, 'semantic_nli_warning_threshold', 0.75)
        warning_geom = getattr(self.config, 'semantic_nli_warning_geom_threshold', 0.1)
        return nli_score > warning_threshold and geom_dist <= warning_geom

    def _resolve_contradiction_index(self) -> int:
        label_map: dict[str, int] = {}

        model_config = getattr(self.nli_model, 'config', None)
        if model_config is not None:
            if hasattr(model_config, 'label2id'):
                label_map.update({str(label).lower(): int(idx) for label, idx in model_config.label2id.items()})
            if hasattr(model_config, 'id2label'):
                label_map.update({str(label).lower(): int(idx) for idx, label in model_config.id2label.items()})

        mapping = getattr(self.config, 'semantic_nli_label_mapping', {})
        mapping_lc = {str(k).lower(): str(v).lower() for k, v in mapping.items()}
        for label, idx in label_map.items():
            canonical = mapping_lc.get(label, label)
            if canonical == 'contradiction':
                return idx

        if 'contradiction' in label_map:
            return label_map['contradiction']

        return getattr(self.config, 'nli_contradiction_index', 0)

    def _project_text(self, text: str) -> np.ndarray:
        normalize = getattr(self.config, 'embedding_normalize', True)
        embedding = self.encoder.encode(text, normalize_embeddings=normalize)
        return self._ensure_unit_norm(embedding)

    def _ensure_unit_norm(self, vector: np.ndarray) -> np.ndarray:
        vector = np.asarray(vector, dtype=float)
        norm = np.linalg.norm(vector)
        if norm == 0.0:
            return vector
        return vector / norm

    def _compute_model_fingerprint(self, source: str) -> str:
        return hashlib.sha256(source.encode('utf-8')).hexdigest()

    def _verify_encoder_signature(self) -> tuple[bool, str]:
        expected = getattr(self.config, 'semantic_embedding_model_signature', None)
        if expected is None:
            return True, ""
        actual = self._compute_model_fingerprint(str(self.config.semantic_embedding_model))
        return actual == expected, actual

    def _combined_distance(self, source_emb: np.ndarray, ref_emb: np.ndarray, premise: str, hypothesis: str) -> tuple[float, float]:
        geom_dist = self._cosine_distance(source_emb, ref_emb)
        nli_confidence = self._nli_contradiction(premise, hypothesis)
        return geom_dist, nli_confidence

    def _check_context_axiom_conflicts(
        self,
        context_input: List[str],
        context_axioms: List[str],
        context_embs: Dict[str, np.ndarray],
        axiom_embs: Dict[str, np.ndarray],
        threshold: float,
    ) -> list[Dict[str, Any]]:
        conflicts: list[Dict[str, Any]] = []
        normalize = getattr(self.config, 'embedding_normalize', True)

        for context in context_input:
            context_embedding = context_embs.get(context)
            if context_embedding is None:
                context_embedding = self.encoder.encode(context, normalize_embeddings=normalize)

            for axiom in context_axioms:
                axiom_embedding = axiom_embs.get(axiom)
                if axiom_embedding is None:
                    axiom_embedding = self.encoder.encode(axiom, normalize_embeddings=normalize)

                geom_distance, _ = self._combined_distance(context_embedding, axiom_embedding, context, axiom)
                if geom_distance > threshold:
                    conflicts.append(
                        {
                            'context': context,
                            'axiom': axiom,
                            'distance': float(geom_distance),
                        }
                    )

        return conflicts

    def compute(
        self,
        audit_input: Any,
        context_input: List[str],
        context_axioms: List[str],
        epsilon: float = 0.0,
        validate_conflicts: bool = False,
    ) -> Tuple[float, float, Any, bool, Dict[str, Any]]:
        semantic_input = str(audit_input) if audit_input is not None else ""
        if not semantic_input.strip():
            return 1.0, 1.0, '[REJECT] Salida vacía o colapso de señal.', True, {
                'error': 'empty_output'
            }

        source_embedding = self._project_text(semantic_input)

        # -----------------------------------------------------------------
        # EVALUACIÓN DE LA COÁLGEBRA TERMINAL
        # -----------------------------------------------------------------
        active_anchor = getattr(self, '_default_anchor', None)
        terminality_error = False
        terminality_error_message = ""

        if active_anchor is not None:
            anchor_embedding = active_anchor.terminal_state
            try:
                dot_product = np.dot(source_embedding, anchor_embedding)
                norm_a = np.linalg.norm(source_embedding)
                norm_b = np.linalg.norm(anchor_embedding)
                if norm_a == 0.0 or norm_b == 0.0:
                    d_terminal = 1.0
                else:
                    d_terminal = float(np.clip(1.0 - (dot_product / (norm_a * norm_b)), 0.0, 1.0))
            except Exception as exc:
                d_terminal = 0.0
                terminality_error = True
                terminality_error_message = str(exc)

            rigidity_threshold = getattr(self.config, 'terminal_rigidity_threshold', 0.01)
            terminality_violation = (not terminality_error) and (d_terminal > (rigidity_threshold + epsilon))
        else:
            d_terminal = 0.0
            terminality_violation = False

        max_axiom_distance = 0.0
        max_context_distance = 0.0
        max_nli_confidence = 0.0
        violated_axioms: list[str] = []
        contradictory_contexts: list[str] = []
        nli_conflicts: list[dict[str, Any]] = []
        nli_warnings: list[dict[str, Any]] = []
        support_found = False

        axiom_embs: Dict[str, np.ndarray] = {}
        context_embs: Dict[str, np.ndarray] = {}

        nli_conflict_threshold = getattr(self.config, 'semantic_nli_conflict_threshold', 0.5)

        for axiom in context_axioms:
            ax_embedding = self._project_text(axiom)
            axiom_embs[axiom] = ax_embedding

            geom_distance, nli_score = self._combined_distance(source_embedding, ax_embedding, axiom, semantic_input)
            max_nli_confidence = max(max_nli_confidence, nli_score)
            max_axiom_distance = max(max_axiom_distance, geom_distance)
            if geom_distance > self.config.context_axiom_conflict_threshold:
                violated_axioms.append(axiom)
            if nli_score > nli_conflict_threshold:
                nli_conflicts.append({'type': 'axiom', 'item': axiom, 'score': float(nli_score)})
            if self._is_nli_warning(geom_distance, nli_score):
                nli_warnings.append({'type': 'axiom', 'item': axiom, 'score': float(nli_score), 'geom_dist': float(geom_distance)})

        for chunk in context_input:
            chunk_embedding = self._project_text(chunk)
            context_embs[chunk] = chunk_embedding

            geom_distance, nli_score = self._combined_distance(source_embedding, chunk_embedding, chunk, semantic_input)
            max_nli_confidence = max(max_nli_confidence, nli_score)
            max_context_distance = max(max_context_distance, geom_distance)
            if geom_distance > self.config.contradiction_snapping_threshold:
                contradictory_contexts.append(chunk)
            if nli_score > nli_conflict_threshold:
                nli_conflicts.append({'type': 'context', 'item': chunk, 'score': float(nli_score)})
            if self._is_nli_warning(geom_distance, nli_score):
                nli_warnings.append({'type': 'context', 'item': chunk, 'score': float(nli_score), 'geom_dist': float(geom_distance)})
            if geom_distance <= self.config.correction_base_tolerance:
                support_found = True

        d_logic_geom = max(max_axiom_distance, max_context_distance, d_terminal)
        d_logic_semantic = max(d_logic_geom, max_nli_confidence)
        D_s = float(np.clip(d_logic_geom, 0.0, 1.0))
        D_f = max_context_distance if context_input else 0.0

        allowable_threshold = self.config.correction_base_tolerance + epsilon
        nli_conflict_triggered = len(nli_conflicts) > 0
        nli_warning_triggered = len(nli_warnings) > 0
        signature_violation = not self._encoder_signature_valid
        snapping_flag = (not support_found) and (
            (max_context_distance > self.config.contradiction_snapping_threshold) or (nli_conflict_triggered and not nli_warning_triggered)
        )
        correction_flag = signature_violation or (D_s > allowable_threshold) or snapping_flag or terminality_violation

        corrected_output: Any = semantic_input
        if signature_violation:
            corrected_output = (
                f"[AUDIT_ERROR] Firma de modelo inválida para semantic_embedding_model=\"{self.config.semantic_embedding_model}\". "
                f"Esperado={getattr(self.config, 'semantic_embedding_model_signature', None)}, "
                f"real={self._encoder_signature_actual}."
            )
        elif correction_flag:
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
        if terminality_error:
            corrected_output = (
                f"[AUDIT_ERROR] Error técnico al evaluar la coálgebra terminal: "
                f"{terminality_error_message}. Se preserva la salida original mientras se registra el fallo."
            )

        metrics = {
            'd_s': D_s,
            'd_logic': d_logic_geom,
            'd_logic_geom': d_logic_geom,
            'd_logic_semantic': d_logic_semantic,
            'd_factual': D_f,
            'd_terminal': d_terminal,
            'terminality_violation': terminality_violation,
            'terminality_error': terminality_error,
            'terminality_error_message': terminality_error_message,
            'encoder_signature_valid': self._encoder_signature_valid,
            'encoder_signature_expected': getattr(self.config, 'semantic_embedding_model_signature', None),
            'encoder_signature_actual': self._encoder_signature_actual,
            'signature_violation': not self._encoder_signature_valid,
            'max_axiom_distance': max_axiom_distance,
            'max_context_distance': max_context_distance,
            'max_context_distance_semantic': max(max_context_distance, max_nli_confidence),
            'max_nli_confidence': max_nli_confidence,
            'violated_axioms': violated_axioms,
            'contradictory_contexts': contradictory_contexts,
            'support_found': support_found,
            'reference_count': len(context_axioms) + len(context_input) + 1,
            'snapping_flag': snapping_flag,
            'nli_conflicts': nli_conflicts,
            'nli_warning_flag': nli_warning_triggered,
            'nli_warnings': nli_warnings,
            'nli_conflict_triggered': nli_conflict_triggered,
            'nli_conflict_threshold': nli_conflict_threshold,
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

    def select_canonical_input(self, canonical_state: "CanonicalState") -> Any:
        return canonical_state.get_representation("semantic")

    def canonical_axis(self) -> str:
        return "semantic"
