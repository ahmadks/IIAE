"""
AxiomExtractor (DSE).

Implementa la Sección 5.2 de la PCT: extracción dinámica de axiomas semánticos
a partir de entradas de auditoría y contexto, usando modelos de embeddings y NLI
(Natural Language Inference) para detectar contradicciones y generar la quíntupla
(S, P, O, Θ, σ) con identificador criptográfico v(α) = H(σ ∥ t).
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional

from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph
from idicoc_notary_core.utils.hashing import sha256_hex


class AxiomExtractor:
    """
    Extractor dinámico de axiomas con soporte semántico (embeddings + NLI).
    """

    def __init__(self, property_graph: PropertyGraph, config: Any | None = None) -> None:
        self.property_graph = property_graph
        self.config = config

        # Cargar configuraciones del modelo de forma robusta
        dse_cfg = getattr(config, "dse_config", None)
        if dse_cfg is not None:
            self.embedding_model_name = getattr(dse_cfg, "embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
            self.nli_model_name = getattr(dse_cfg, "nli_model", "facebook/bart-large-mnli")
            self.nli_conflict_threshold = getattr(dse_cfg, "nli_conflict_threshold", 0.5)
        else:
            self.embedding_model_name = getattr(config, "semantic_embedding_model", "sentence-transformers/all-MiniLM-L6-v2")
            self.nli_model_name = getattr(config, "semantic_nli_model", "facebook/bart-large-mnli")
            self.nli_conflict_threshold = getattr(config, "semantic_nli_conflict_threshold", 0.5)

        # Carga diferida de modelos
        self._embedder: Any = None
        self._nli_pipeline: Any = None
        self._models_available: bool = True

    def _get_embedder(self) -> Any:
        if self._embedder is None and self._models_available:
            try:
                from idicoc_notary_core.utils.embedding_service import EmbeddingService
                self._embedder = EmbeddingService().get_embedder(self.embedding_model_name)
                if self._embedder is None:
                    raise ImportError("El servicio no pudo cargar el modelo.")
            except Exception:
                self._models_available = False
        return self._embedder

    def _get_nli(self) -> Any:
        if self._nli_pipeline is None and self._models_available:
            try:
                from transformers import pipeline as hf_pipeline
                self._nli_pipeline = hf_pipeline(
                    "zero-shot-classification",
                    model=self.nli_model_name,
                )
            except Exception:
                self._models_available = False
        return self._nli_pipeline

    def extract_from_context(
        self,
        context_input: Optional[list[str]] = None,
        context_axioms: Optional[list[str]] = None,
    ) -> PropertyGraph:
        """
        Extrae y precomputa axiomas exclusivamente a partir del contexto estático.
        Nunca recibe el audit_input en tiempo de ejecución.
        """
        context_input = context_input or []
        context_axioms = context_axioms or []
        timestamp = datetime.now(timezone.utc).isoformat()
        
        embedder = self._get_embedder()

        # 1. Axiomas desde context_axioms predefinidos
        for axiom_text in context_axioms:
            if not isinstance(axiom_text, str):
                axiom_text = str(axiom_text)
            ax = self._axiom_from_text(axiom_text, axiom_type="protocol", timestamp=timestamp)
            if embedder is not None:
                try:
                    vec = embedder.encode(axiom_text, normalize_embeddings=True)
                    ax["embedding"] = vec.tolist()
                except Exception:
                    pass
            self.property_graph.add_axiom(ax["axiom_id"], ax)

        # 2. Axiomas extraídos de context_input
        for text in context_input:
            if not isinstance(text, str) or not text.strip():
                continue
            ax = self._axiom_from_text(text, axiom_type="fact", timestamp=timestamp)
            if embedder is not None:
                try:
                    vec = embedder.encode(text, normalize_embeddings=True)
                    ax["embedding"] = vec.tolist()
                except Exception:
                    pass
            self.property_graph.add_axiom(ax["axiom_id"], ax)

        # 3. Detección de contradicciones vía NLI en el contexto base
        if len(context_input) >= 2:
            contradiction_axioms = self._detect_contradictions(context_input, timestamp)
            for ax in contradiction_axioms:
                self.property_graph.add_axiom(ax["axiom_id"], ax)

        self.property_graph.detect_conflicts()
        return self.property_graph

    def _build_base_axiom(
        self, raw_text: str, canonical_text: str, timestamp: str
    ) -> list[dict[str, Any]]:
        subject = type(raw_text).__name__
        obj = type(canonical_text).__name__
        predicate = "transforms_to"
        scope = "session"
        axiom_type = "logic"
        polarity = "affirmative"
        hardness = "soft"
        priority = 1

        sigma = f"{subject}|{predicate}|{obj}|{scope}|{axiom_type}|{polarity}"
        structural_signature = sha256_hex(sigma)
        axiom_id = sha256_hex(structural_signature + "||" + timestamp)

        return [{
            "axiom_id": axiom_id,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "scope": scope,
            "axiom_type": axiom_type,
            "polarity": polarity,
            "hardness": hardness,
            "priority": priority,
            "timestamp": timestamp,
            "structural_signature": structural_signature,
            "axiom_version": axiom_id,
        }]

    def _axiom_from_text(
        self,
        text: str,
        axiom_type: str = "fact",
        timestamp: str = "",
    ) -> dict[str, Any]:
        """
        Construye una quíntupla (S, P, O, Θ, σ) a partir de texto libre.
        """
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        text_lower = text.lower().strip()

        # Clasificación de polaridad, hardness, prioridad
        if any(kw in text_lower for kw in ("not ", "never ", "prohibit", "forbidden", "must not", "no ")):
            polarity = "negative"
            hardness = "hard"
            priority = 10
        elif any(kw in text_lower for kw in ("must ", "always ", "required", "mandatory", "obligatory")):
            polarity = "affirmative"
            hardness = "hard"
            priority = 9
        elif any(kw in text_lower for kw in ("should ", "prefer", "recommend")):
            polarity = "affirmative"
            hardness = "soft"
            priority = 5
        else:
            polarity = "affirmative"
            hardness = "soft"
            priority = 1

        # Tipo de axioma por palabras clave
        if any(kw in text_lower for kw in ("after", "before", "during", "when", "at time")):
            axiom_type = "temporal"
        elif any(kw in text_lower for kw in ("is a", "is an", "belongs to", "type of")):
            axiom_type = "world"
        elif any(kw in text_lower for kw in ("protocol", "policy", "rule")):
            axiom_type = "protocol"

        tokens = text_lower.split()
        subject = tokens[0] if tokens else "unknown"
        obj = tokens[-1] if len(tokens) > 1 else "unknown"
        predicate = "states"
        scope = "session"

        # Generar quíntupla (S, P, O, Θ, σ) y versión criptográfica H(σ ∥ t)
        sigma = f"{subject}|{predicate}|{obj}|{scope}|{axiom_type}|{polarity}|{text[:64]}"
        structural_signature = sha256_hex(sigma)
        axiom_id = sha256_hex(structural_signature + "||" + timestamp)

        return {
            "axiom_id": axiom_id,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "scope": scope,
            "axiom_type": axiom_type,
            "polarity": polarity,
            "hardness": hardness,
            "priority": priority,
            "timestamp": timestamp,
            "structural_signature": structural_signature,
            "axiom_version": axiom_id,
            "source_text": text[:256],
        }

    def _detect_contradictions(
        self, fragments: list[str], timestamp: str
    ) -> list[dict[str, Any]]:
        nli = self._get_nli()
        if nli is None or len(fragments) < 2:
            return []

        contradiction_axioms: list[dict[str, Any]] = []
        for i, premise in enumerate(fragments):
            for hypothesis in fragments[i + 1:]:
                try:
                    result = nli(
                        hypothesis,
                        candidate_labels=["contradiction", "entailment", "neutral"],
                        hypothesis_template="{}",
                    )
                    scores = dict(zip(result["labels"], result["scores"]))
                    contradiction_score = scores.get("contradiction", 0.0)
                    if contradiction_score >= self.nli_conflict_threshold:
                        ax = self._axiom_from_text(
                            f"CONTRADICTION: '{premise[:64]}' vs '{hypothesis[:64]}'",
                            axiom_type="logic",
                            timestamp=timestamp,
                        )
                        ax["polarity"] = "negative"
                        ax["hardness"] = "hard"
                        ax["priority"] = 10
                        ax["nli_contradiction_score"] = contradiction_score
                        contradiction_axioms.append(ax)
                except Exception:
                    continue

        return contradiction_axioms

    def _build_semantic_axiom(
        self,
        raw_text: str,
        canonical_text: str,
        timestamp: str,
    ) -> dict[str, Any] | None:
        embedder = self._get_embedder()
        if embedder is None or not raw_text or not canonical_text:
            return None

        try:
            import numpy as np
            vecs = embedder.encode([raw_text, canonical_text], normalize_embeddings=True)
            cosine_sim = float(np.dot(vecs[0], vecs[1]))
            polarity = "affirmative" if cosine_sim >= 0.5 else "negative"
            sigma = f"semantic|{raw_text[:32]}|{canonical_text[:32]}|{cosine_sim:.4f}"
            structural_signature = sha256_hex(sigma)
            axiom_id = sha256_hex(structural_signature + "||" + timestamp)
            return {
                "axiom_id": axiom_id,
                "subject": "input",
                "predicate": "semantically_aligned_with",
                "object": "canonical",
                "scope": "session",
                "axiom_type": "logic",
                "polarity": polarity,
                "hardness": "soft",
                "priority": 3,
                "timestamp": timestamp,
                "structural_signature": structural_signature,
                "axiom_version": axiom_id,
                "cosine_similarity": cosine_sim,
            }
        except Exception:
            return None

    @staticmethod
    def _to_text(obj: Any) -> str:
        if obj is None:
            return ""
        if isinstance(obj, str):
            return obj
        if hasattr(obj, "data"):
            return str(obj.data)
        if hasattr(obj, "semantic_vector"):
            return str(obj.semantic_vector)
        return str(obj)
