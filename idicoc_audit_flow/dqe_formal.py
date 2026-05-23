from __future__ import annotations
from typing import Any, List, Tuple

import numpy as np
import torch
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer


class DQEEngineFormal:
    """
    DEVIATION QUANTIFICATION ENGINE (DQE) - IMPLEMENTACIÓN COALGEBRAICA FORMAL.
    Fiel al Marco Ontológico (MAO), al CMC y a los Teoremas de Conformidad.

    Este módulo actúa como el Funtor de Observación en el Wrapper, evaluando la
    coherencia de la salida estocástica frente al Grafo de Propiedades (Axiomas)
    y el contexto RAG recuperado.
    """

    def __init__(
        self,
        embedding_model_name: str,
        nli_model_name: str,
        delta_fp: float = 0.15,
    ):
        self.encoder = SentenceTransformer(embedding_model_name)
        self.nli_tokenizer = AutoTokenizer.from_pretrained(nli_model_name)
        self.nli_model = AutoModelForSequenceClassification.from_pretrained(nli_model_name)
        self.delta_fp = delta_fp

    def _compute_cosine_distance(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        dot_product = np.dot(vec_a, vec_b)
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 1.0
        similarity = dot_product / (norm_a * norm_b)
        return float(1.0 - similarity)

    def _evaluate_nli_contradiction(self, premise: str, hypothesis: str) -> float:
        inputs = self.nli_tokenizer(premise, hypothesis, return_tensors="pt", truncation=True)
        with torch.no_grad():
            outputs = self.nli_model(**inputs)

        probs = torch.softmax(outputs.logits, dim=-1).squeeze().tolist()
        if isinstance(probs, float):
            return probs
        return float(probs[0])

    def quantify_dissonance(
        self,
        raw_response: str,
        axioms: List[str],
        rag_chunks: List[str],
        epsilon: float = 0.0,
    ) -> Tuple[float, float, str, bool]:
        if not raw_response.strip():
            return 1.0, 1.0, "[REJECT] Salida vacía o colapso de señal.", True

        response_embedding = self.encoder.encode(raw_response, normalize_embeddings=True)
        ds_distances: list[float] = []
        contradiction_with_axioms = 0.0

        if axioms:
            axiom_embeddings = self.encoder.encode(axioms, normalize_embeddings=True)
            for act_axiom, ax_emb in zip(axioms, axiom_embeddings):
                dist = self._compute_cosine_distance(response_embedding, ax_emb)
                ds_distances.append(dist)
                nli_score = self._evaluate_nli_contradiction(premise=act_axiom, hypothesis=raw_response)
                contradiction_with_axioms = max(contradiction_with_axioms, nli_score)
            max_ds_dist = float(np.max(ds_distances)) if ds_distances else 0.0
            # Fórmula coalgebraica (Anexo J): D_s = λ2 · d_logic
            # d_logic = sup(max_geometric_dist, max_logical_contradiction) sobre los axiomas.
            # λ_inv=0 (sin V̂), λ_logic=1.0, λ_temporal=0 (reservado).
            d_logic = max(max_ds_dist, contradiction_with_axioms)
            D_s = d_logic
        else:
            d_logic = 0.0
            D_s = 0.0

        df_distances: list[float] = []
        support_found = False
        max_rag_contradiction = 0.0

        if rag_chunks:
            rag_embeddings = self.encoder.encode(rag_chunks, normalize_embeddings=True)
            for chunk, chunk_emb in zip(rag_chunks, rag_embeddings):
                dist = self._compute_cosine_distance(response_embedding, chunk_emb)
                df_distances.append(dist)
                nli_score = self._evaluate_nli_contradiction(premise=chunk, hypothesis=raw_response)
                max_rag_contradiction = max(max_rag_contradiction, nli_score)
                if dist <= self.delta_fp:
                    support_found = True
            min_df_dist = float(np.min(df_distances)) if df_distances else 1.0
            D_f = max(min_df_dist, max_rag_contradiction)
        else:
            D_f = 1.0

        allowable_threshold = self.delta_fp + epsilon
        is_violating_axioms = D_s > allowable_threshold
        is_hallucinating_rag = (
            D_f > allowable_threshold
            or (not support_found and max_rag_contradiction > 0.5)
        )

        if is_violating_axioms:
            return (
                D_s,
                D_f,
                "[CRITICAL REJECTION] La salida viola los axiomas estructurales inyectados en el sistema.",
                True,
            )

        if is_hallucinating_rag:
            corrected_output = (
                f"[SNAPPING ACTIVE] La respuesta generada por el modelo comercial incurrió en una "
                f"disonancia factual insostenible (D_f = {D_f:.4f}). Estado revertido al contexto RAG canónico primario: "
                f"'{rag_chunks[0] if rag_chunks else 'Sin soporte factual disponible'}'"
            )
            return D_s, D_f, corrected_output, True

        return D_s, D_f, raw_response, False
