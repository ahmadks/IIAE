"""
PolicyExtractor (DSE).

Implementa la Sección 5.2 de la PCT: extracción dinámica de políticas semánticas
a partir de entradas de auditoría y contexto, usando modelos de embeddings y NLI
(Natural Language Inference) para detectar contradicciones y generar la quíntupla
(S, P, O, Θ, σ) con identificador criptográfico v(α) = H(σ ∥ t).
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Optional

from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph
from idicoc_notary_core.utils.hashing import sha256_hex
from idicoc_notary_core.kernel.dse.extractor_strategy import ExtractorStrategy
from idicoc_notary_core.utils.logger import get_logger

logger = get_logger("kernel.dse")


class PolicyExtractor:
    """
    Extractor dinámico de politicas con soporte semántico (embeddings + NLI).
    """

    def __init__(self, property_graph: PropertyGraph, config: Any | None = None) -> None:
        self.property_graph = property_graph
        self.config = config

        # Cargar configuraciones del modelo de forma robusta
        dse_cfg = getattr(config, "dse_config", None)
        if dse_cfg is not None:
            self.embedding_model_name = getattr(
                dse_cfg, "embedding_model", "sentence-transformers/all-MiniLM-L6-v2"
            )
            self.nli_model_name = getattr(dse_cfg, "nli_model", "facebook/bart-large-mnli")
            self.nli_conflict_threshold = getattr(dse_cfg, "nli_conflict_threshold", 0.5)
        else:
            self.embedding_model_name = getattr(
                config, "semantic_embedding_model", "sentence-transformers/all-MiniLM-L6-v2"
            )
            self.nli_model_name = getattr(config, "semantic_nli_model", "facebook/bart-large-mnli")
            self.nli_conflict_threshold = getattr(config, "semantic_nli_conflict_threshold", 0.5)

        # Carga diferida de modelos
        self._embedder: Any = None
        self._nli_pipeline: Any = None
        self._models_available: bool = True
        # Strategy for extraction decisions (NLI vs fallback)
        self.extractor_strategy = ExtractorStrategy(config)

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
        # Preferir pipeline NLI centralizado desde config si está disponible
        try:
            if self.config is not None:
                cfg_nli = getattr(self.config, "nli_pipeline", None)
                if cfg_nli is not None:
                    return cfg_nli
        except Exception:
            pass

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
        context_policies: Optional[list[str]] = None,
    ) -> PropertyGraph:
        """
        Extrae y precomputa políticas exclusivamente a partir del contexto estático.
        Nunca recibe el audit_input en tiempo de ejecución.
        """
        context_input = context_input or []
        context_policies = context_policies or []
        timestamp = datetime.now(timezone.utc).isoformat()

        embedder = self._get_embedder()

        # 1. Políticas desde context_policies predefinidos
        for policy_text in context_policies:
            if not isinstance(policy_text, str):
                policy_text = str(policy_text)
            policy_dict = self._policy_from_text(
                policy_text, policy_type="protocol", timestamp=timestamp
            )
            if embedder is not None:
                try:
                    vec = embedder.encode(policy_text)
                    policy_dict["embedding"] = vec.tolist()
                except Exception as e:
                    logger.error(
                        f"[DSE] Critical failure: could not generate embedding for policy text '{policy_text}': {e}"
                    )
                    raise RuntimeError(f"Embedding generation failed: {e}") from e
            self.property_graph.add_policy(policy_dict["policy_id"], policy_dict)

        # 2. Políticas extraídas de context_input
        for text in context_input:
            if not isinstance(text, str) or not text.strip():
                continue
            policy_dict = self._policy_from_text(text, policy_type="fact", timestamp=timestamp)
            if embedder is not None:
                try:
                    vec = embedder.encode(text)
                    policy_dict["embedding"] = vec.tolist()
                except Exception as e:
                    logger.error(
                        f"[DSE] Critical failure: could not generate embedding for context text '{text}': {e}"
                    )
                    raise RuntimeError(f"Embedding generation failed: {e}") from e
            self.property_graph.add_policy(policy_dict["policy_id"], policy_dict)

        # 3. Detección de contradicciones vía NLI en el contexto base
        if len(context_input) >= 2:
            contradiction_policies = self._detect_contradictions(context_input, timestamp)
            for policy_dict in contradiction_policies:
                self.property_graph.add_policy(policy_dict["policy_id"], policy_dict)

        self.property_graph.detect_conflicts()
        return self.property_graph

    def _build_base_policy(
        self, raw_text: str, canonical_text: str, timestamp: str
    ) -> list[dict[str, Any]]:
        subject = type(raw_text).__name__
        obj = type(canonical_text).__name__
        predicate = "transforms_to"
        scope = "session"
        policy_type = "logic"
        polarity = "affirmative"
        hardness = "soft"
        priority = 1

        sigma = f"{subject}|{predicate}|{obj}|{scope}|{policy_type}|{polarity}"
        structural_signature = sha256_hex(sigma)
        policy_id = sha256_hex(structural_signature + "||" + timestamp)

        return [
            {
                "policy_id": policy_id,
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "scope": scope,
                "policy_type": policy_type,
                "polarity": polarity,
                "hardness": hardness,
                "priority": priority,
                "timestamp": timestamp,
                "structural_signature": structural_signature,
                "policy_version": policy_id,
            }
        ]

    def _policy_from_text(
        self,
        text: str,
        policy_type: str = "fact",
        timestamp: str = "",
    ) -> dict[str, Any]:
        """
        Construye una quíntupla (S, P, O, Θ, σ) a partir de texto libre.
        """
        if not timestamp:
            timestamp = datetime.now(timezone.utc).isoformat()

        text_lower = text.lower().strip()

        # Delegate extraction decisions to strategy
        extract_info = self.extractor_strategy.analyze(text)
        polarity = extract_info.get("polarity", "affirmative")
        hardness = extract_info.get("hardness", "soft")
        priority = extract_info.get("priority", 1)
        extraction_mode = extract_info.get("extraction_mode", "regex_fallback")

        # Tipo de política por palabras clave
        if any(kw in text_lower for kw in ("after", "before", "during", "when", "at time")):
            policy_type = "temporal"
        elif any(kw in text_lower for kw in ("is a", "is an", "belongs to", "type of")):
            policy_type = "world"
        elif any(kw in text_lower for kw in ("protocol", "policy", "rule")):
            policy_type = "protocol"

        tokens = text_lower.split()
        subject = tokens[0] if tokens else "unknown"
        obj = tokens[-1] if len(tokens) > 1 else "unknown"
        predicate = "states"
        scope = "session"

        # Generar quíntupla (S, P, O, Θ, σ) y versión criptográfica H(σ ∥ t)
        # Usamos el hash SHA-256 del texto completo para garantizar resistencia a colisiones.
        # Truncar el texto (text[:64]) es peligroso cuando múltiples normas (GDPR, ISO)
        # comparten preámbulos normativos idénticos de más de 64 caracteres.
        text_hash = sha256_hex(text)
        sigma = f"{subject}|{predicate}|{obj}|{scope}|{policy_type}|{polarity}|{text_hash}"
        structural_signature = sha256_hex(sigma)
        policy_id = sha256_hex(structural_signature + "||" + timestamp)

        return {
            "policy_id": policy_id,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "scope": scope,
            "policy_type": policy_type,
            "polarity": polarity,
            "hardness": hardness,
            "priority": priority,
            "timestamp": timestamp,
            "structural_signature": structural_signature,
            "policy_version": policy_id,
            "source_text": text[:256],
            # Campo de trazabilidad forense: permite al auditor distinguir políticas
            # certificadas por el oráculo NLI de aquellas derivadas por reglas heurísticas.
            # Un valor 'regex_fallback' en el Merkle DAG es una señal de alerta para
            # revisores ISO 42001 / ETSI de que esa política puede no capturar violaciones
            # semánticas (solo léxicas).
            "extraction_mode": extraction_mode,
        }

    def _detect_contradictions(self, fragments: list[str], timestamp: str) -> list[dict[str, Any]]:
        return self.extractor_strategy.detect_contradictions(fragments)

    def _build_semantic_policy(
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

            vecs = np.asarray(embedder.encode([raw_text, canonical_text]), dtype=float)
            # Normalización L2 explícita: garantiza que np.dot sea el coseno real,
            # no el producto escalar bruto. Crítico si el modelo retorna vectores no
            # normalizados (cuantización FP16, fine-tuning, o variantes de SentenceTransformers).
            norms = np.linalg.norm(vecs, axis=1, keepdims=True)
            vecs = vecs / np.where(norms < 1e-12, 1.0, norms)
            cosine_sim = float(np.dot(vecs[0], vecs[1]))
            polarity = "affirmative" if cosine_sim >= 0.5 else "negative"
            sigma = f"semantic|{raw_text}|{canonical_text}|{cosine_sim:.4f}"
            structural_signature = sha256_hex(sigma)
            policy_id = sha256_hex(structural_signature + "||" + timestamp)
            return {
                "policy_id": policy_id,
                "subject": "input",
                "predicate": "semantically_aligned_with",
                "object": "canonical",
                "scope": "session",
                "policy_type": "logic",
                "polarity": polarity,
                "hardness": "soft",
                "priority": 3,
                "timestamp": timestamp,
                "structural_signature": structural_signature,
                "policy_version": policy_id,
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
