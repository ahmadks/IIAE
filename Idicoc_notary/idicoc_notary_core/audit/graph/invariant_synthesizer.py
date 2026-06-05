"""
Sintetizador de Invariantes Combinatorio - Fase 1 (Cold Loop).

Compila políticas textuales en matrices estáticas de token_ids prohibidos (W_bank).
Esta compilación ocurre UNA SOLA VEZ durante la inicialización del sistema.
Durante la Fase 3 (Hot Loop), el DeterministicMUXLogitsProcessor aplica
una máscara O(1) usando W_bank para garantizar contenencia de la red neuronal.

Especificación: IDICOC, Sección 2.3 (Contención Sub-Simbólica)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
import re
import numpy as np
import os
import json
from idicoc_notary_core.utils.logger import get_logger

logger = get_logger("audit.invariant_synthesizer")


@dataclass
class InvariantToken:
    """Representación de un token individual prohibido."""

    token_id: int
    token_text: str
    source_policy: str
    policy_id: Optional[str] = None
    hardness: str = "soft"  # "soft" | "hard"
    priority: int = 1


@dataclass
class PolicyCompilationResult:
    """Resultado de la compilación de una política individual."""

    policy_id: Optional[str]
    policy_text: str
    forbidden_tokens: List[InvariantToken]
    compilation_status: str  # "success" | "warning" | "error"
    message: str


class InvariantSynthesizer:
    """
    Compilador determinista de políticas → matriz de tokens prohibidos (W_bank).

    Flujo:
    1. Lee políticas textuales (context_policies)
    2. Tokeniza cada política con el tokenizador de Llama
    3. Extrae conceptos violados y sus sinónimos
    4. Construye matriz indexada W_bank[token_id] = (hardness, priority)
    5. Persiste W_bank en memoria GPU para acceso O(1) en Phase 3
    """

    def __init__(
        self,
        tokenizer: Any = None,  # Tokenizer-like object; fallback applied if None
        embedding_service: Optional[Any] = None,  # Para análisis semántico avanzado
        embedding_threshold: float = 0.65,
        precompute_vocab_embeddings: bool = False,
        vocab_cache_path: Optional[str] = None,
    ) -> None:
        """
        Inicializa el sintetizador.

        Args:
            tokenizer: Tokenizador de Llama (transformers.AutoTokenizer)
            embedding_service: Servicio de embeddings opcional para análisis semántico
        """
        # Allow a tokenizer-agnostic fallback to keep core independent of transformers
        if tokenizer is None:
            # Simple whitespace tokenizer fallback with incremental vocab ids
            class _FallbackTokenizer:
                def __init__(self):
                    self._vocab = {}

                def encode(self, text: str):
                    ids = []
                    for tok in text.split():
                        if tok not in self._vocab:
                            self._vocab[tok] = len(self._vocab) + 1
                        ids.append(self._vocab[tok])
                    return ids

                @property
                def vocab_size(self):
                    return max(1, len(self._vocab))

                def __len__(self):
                    return self.vocab_size

            tokenizer = _FallbackTokenizer()

        self.tokenizer = tokenizer
        self.embedding_service = embedding_service
        if self.embedding_service is None:
            raise ValueError(
                "EmbeddingService es obligatorio para InvariantSynthesizer. "
                "Configure un proveedor de embeddings en AuditConfig."
            )
        self.w_bank: Dict[int, Tuple[str, int]] = {}  # token_id → (hardness, priority)
        self.compilation_log: List[PolicyCompilationResult] = []
        self.vocab_size = len(tokenizer) if hasattr(tokenizer, "__len__") else tokenizer.vocab_size
        # Umbral de similitud para selección semántica de tokens/frases
        self.embedding_threshold = embedding_threshold
        # Vocab embeddings cache (opcional, calculado sólo si solicitado)
        self.vocab_tokens_text: List[str] = []
        self.vocab_token_ids: List[int] = []
        self.vocab_embeddings: Optional[np.ndarray] = None
        self.vocab_cache_path = vocab_cache_path
        self.kd_tree: Optional[Any] = None

        if precompute_vocab_embeddings:
            try:
                self._get_or_compute_vocab_embeddings(cache_path=vocab_cache_path)
            except Exception as e:
                logger.warning(f"Fallo al precomputar embeddings de vocabulario: {e}")

        logger.info(f"[Invariant Synthesizer] Inicializado. Vocab size: {self.vocab_size}")

    def compile_policies(
        self,
        policies: List[Dict[str, Any]],
        include_variants: bool = True,
        hardness_multiplier: float = 1.0,
    ) -> Dict[int, Tuple[str, int]]:
        """
        Compila una lista de políticas en matriz W_bank.

        Args:
            policies: Lista de dicts con {text, hardness, priority, ...}
            include_variants: Si True, genera variantes sintácticas de cada política
            hardness_multiplier: Escala de prioridad según dureza (soft=1.0, hard=2.0)

        Returns:
            Diccionario W_bank: {token_id: (hardness, priority)}
        """
        self.w_bank.clear()
        self.compilation_log.clear()

        logger.info(f"[Phase 1 - Cold Loop] Compilando {len(policies)} políticas...")

        total_tokens = 0
        hard_policies = sum(1 for p in policies if p.get("hardness") == "hard")
        soft_policies = len(policies) - hard_policies

        for policy in policies:
            result = self._compile_single_policy(
                policy,
                include_variants=include_variants,
                hardness_multiplier=hardness_multiplier,
            )
            self.compilation_log.append(result)
            total_tokens += len(result.forbidden_tokens)

        logger.info(
            f"[Phase 1 - Cold Loop] Compilación completada. "
            f"Matriz W_bank contiene {len(self.w_bank)} tokens prohibidos. "
            f"Políticas hard={hard_policies}, soft={soft_policies}, "
            f"Tokens únicos indexados={len(self.w_bank)}"
        )

        return self.w_bank

    def _compile_single_policy(
        self,
        policy: Dict[str, Any],
        include_variants: bool = True,
        hardness_multiplier: float = 1.0,
    ) -> PolicyCompilationResult:
        """Compila una política individual."""
        policy_text = policy.get("text", "")
        policy_id = policy.get("id") or policy.get("policy_id")
        hardness = policy.get("hardness", "soft")
        priority = int(policy.get("priority", 1))

        if not policy_text:
            return PolicyCompilationResult(
                policy_id=policy_id,
                policy_text=policy_text,
                forbidden_tokens=[],
                compilation_status="warning",
                message="Política vacía, ignorada.",
            )

        forbidden_tokens: List[InvariantToken] = []

        try:
            # Tokenizar la política base
            base_tokens = self._extract_concept_tokens(policy_text, policy_id, hardness, priority)
            forbidden_tokens.extend(base_tokens)

            # Si se solicita, generar variantes semánticas
            if include_variants and self.embedding_service:
                variant_tokens = self._generate_semantic_variants(
                    policy_text, policy_id, hardness, priority
                )
                forbidden_tokens.extend(variant_tokens)

            # Agregar tokens a W_bank
            for token_info in forbidden_tokens:
                priority_scaled = token_info.priority
                if hardness == "hard":
                    priority_scaled = int(priority_scaled * hardness_multiplier)

                # Si el token ya existe, mantener la máxima prioridad
                if token_info.token_id in self.w_bank:
                    existing_hardness, existing_priority = self.w_bank[token_info.token_id]
                    # Preferir "hard" sobre "soft"
                    new_hardness = (
                        "hard" if hardness == "hard" or existing_hardness == "hard" else "soft"
                    )
                    # Mantener máxima prioridad
                    new_priority = max(priority_scaled, existing_priority)
                    self.w_bank[token_info.token_id] = (new_hardness, new_priority)
                else:
                    self.w_bank[token_info.token_id] = (hardness, priority_scaled)

            return PolicyCompilationResult(
                policy_id=policy_id,
                policy_text=policy_text,
                forbidden_tokens=forbidden_tokens,
                compilation_status="success",
                message=f"Compilada exitosamente. {len(forbidden_tokens)} tokens prohibidos.",
            )

        except Exception as e:
            logger.error(f"Error compilando política {policy_id}: {e}")
            return PolicyCompilationResult(
                policy_id=policy_id,
                policy_text=policy_text,
                forbidden_tokens=[],
                compilation_status="error",
                message=f"Error durante compilación: {str(e)}",
            )

    def _extract_concept_tokens(
        self,
        text: str,
        policy_id: Optional[str],
        hardness: str,
        priority: int,
    ) -> List[InvariantToken]:
        """Extrae tokens invariantes evaluando su distancia topológica a la política.

        El filtrado de stopwords y términos irrelevantes se realiza implícitamente:
        en un espacio de embeddings semánticos, los artículos, preposiciones y
        conjunciones tienen baja similitud coseno con textos de política específicos
        y quedan fuera del radio semántico del KDTree.
        """
        tokens: List[InvariantToken] = []

        try:
            # 1. Consulta geométrica en O(log V): tokens del vocabulario que caen
            # dentro del radio semántico de la política (distancia topológica <= threshold).
            # Las stopwords son filtradas naturalmente por distancia matemática, sin
            # heurísticas lingüísticas.
            similar_token_ids = self.query_similar_tokens(text, self.embedding_threshold)

            if not similar_token_ids:
                logger.warning(
                    f"[Ambiguity Alert] La política '{text[:50]}...' no generó un ancla vectorial fuerte. "
                    f"Aumente la densidad de la política o baje el umbral."
                )
                return tokens

            # 2. Registrar los tokens encontrados en el W_bank
            for token_id in similar_token_ids[:50]:  # Límite de seguridad anti-flooding
                try:
                    token_text = self.tokenizer.decode([token_id])
                except Exception:
                    token_text = f"<UNK:{token_id}>"

                tokens.append(
                    InvariantToken(
                        token_id=token_id,
                        token_text=token_text,
                        source_policy=text[:50] + ("..." if len(text) > 50 else ""),
                        policy_id=policy_id,
                        hardness=hardness,
                        priority=priority,
                    )
                )

        except Exception as e:
            logger.error(f"Error topológico extrayendo tokens de '{text}': {e}")

        return tokens

    def _get_or_compute_vocab_embeddings(self, cache_path: Optional[str] = None) -> np.ndarray:
        """Computa y opcionalmente cachea las proyecciones de embeddings para todo el vocabulario.

        Args:
            cache_path: Ruta base (sin extensión) para guardar meta + numpy. Si se pasa y los
                archivos existen, los cargará en lugar de recomputar.

        Returns:
            Matriz numpy de shape (V, D) con embeddings de vocabulario.
        """
        if not hasattr(self.tokenizer, "get_vocab"):
            raise RuntimeError(
                "El tokenizador no expone `get_vocab()`, imposible precalcular vocab."
            )

        meta_path = None
        emb_path = None
        if cache_path:
            meta_path = f"{cache_path}.meta.json"
            emb_path = f"{cache_path}.npy"
            if os.path.exists(meta_path) and os.path.exists(emb_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    tokens = meta.get("tokens", [])
                    token_ids = meta.get("token_ids", [])
                    embeddings = np.load(emb_path)
                    # Normalize for KDTree L2-based cosine mapping
                    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                    norms = np.where(norms < 1e-12, 1.0, norms)
                    embeddings = embeddings / norms

                    from scipy.spatial import KDTree

                    self.vocab_tokens_text = tokens
                    self.vocab_token_ids = token_ids
                    self.vocab_embeddings = embeddings
                    self.kd_tree = KDTree(embeddings)
                    return embeddings
                except Exception as e:
                    logger.warning(
                        f"No se pudo cargar cache de vocab ({meta_path},{emb_path}): {e}"
                    )

        vocab = self.tokenizer.get_vocab()
        tokens_text = list(vocab.keys())
        token_ids = [vocab[t] for t in tokens_text]

        # Limpiar tokens especiales para una mejor proyección semántica (heurística)
        clean_tokens = [t.replace("Ġ", "").replace(" ", "") for t in tokens_text]

        # Calcular embeddings en batch
        try:
            embs = np.asarray(self.embedding_service.encode(clean_tokens), dtype=float)
        except TypeError:
            # Algunos servicios usan convert_to_numpy kwarg
            embs = np.asarray(
                self.embedding_service.encode(clean_tokens, convert_to_numpy=True), dtype=float
            )

        # Normalize the embeddings for KDTree L2-based cosine mapping
        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        norms = np.where(norms < 1e-12, 1.0, norms)
        embs = embs / norms

        # Guardar en atributos
        self.vocab_tokens_text = tokens_text
        self.vocab_token_ids = token_ids
        self.vocab_embeddings = embs
        from scipy.spatial import KDTree

        self.kd_tree = KDTree(embs)

        # Guardar cache si se especificó path
        if cache_path:
            try:
                meta = {"tokens": tokens_text, "token_ids": token_ids}
                with open(f"{cache_path}.meta.json", "w", encoding="utf-8") as f:
                    json.dump(meta, f, ensure_ascii=False)
                np.save(f"{cache_path}.npy", embs)
            except Exception as e:
                logger.warning(f"No se pudo escribir cache de vocab: {e}")

        return embs

    def _generate_semantic_variants(
        self,
        policy_text: str,
        policy_id: Optional[str],
        hardness: str,
        priority: int,
    ) -> List[InvariantToken]:
        """Genera variantes semánticas de una política usando query_similar_tokens sobre paráfrasis.

        Cada paráfrasis sintética es consultada contra el KDTree global del vocabulario.
        Los tokens retornados son geométricamente próximos a la variante en el espacio de embeddings.
        """
        variants: List[InvariantToken] = []

        if not self.embedding_service:
            return variants

        try:
            synthetic_variants = self._generate_synthetic_paraphrases(policy_text)

            seen_variant_ids: Set[int] = set()
            for variant in synthetic_variants:
                # Consulta geométrica: tokens similares a la paráfrasis en O(log V)
                similar_ids = self.query_similar_tokens(variant, self.embedding_threshold)
                for token_id in similar_ids[:5]:  # Limitar a 5 tokens por variante
                    if token_id in seen_variant_ids:
                        continue
                    seen_variant_ids.add(token_id)
                    try:
                        token_text = self.tokenizer.decode([token_id])
                    except Exception:
                        token_text = f"<UNK:{token_id}>"
                    variants.append(
                        InvariantToken(
                            token_id=token_id,
                            token_text=token_text,
                            source_policy=f"variant:{policy_text[:40]}...",
                            policy_id=policy_id,
                            hardness=hardness,
                            priority=max(
                                1, priority - 1
                            ),  # Variantes con prioridad ligeramente menor
                        )
                    )

        except Exception as e:
            logger.warning(f"Error generando variantes de '{policy_text}': {e}")

        return variants

    SYNONYM_MAP = {
        "prohibit": ["forbid", "ban", "restrict", "prevent", "disallow", "bar", "block"],
        "never": ["not", "at no time", "under no circumstances"],
        "always": ["constantly", "forever", "without exception", "invariably"],
        "allow": ["permit", "let", "authorize", "approve", "sanction"],
        "restricted": ["limited", "confined", "curbed", "bounded"],
        "required": ["mandatory", "compulsory", "obligatory", "needed", "essential"],
        "access": ["entry", "admission", "reach"],
        "permit": ["allow", "authorize", "license"],
        "deny": ["refuse", "reject", "decline", "withhold"],
    }

    def _generate_synthetic_paraphrases(self, text: str) -> List[str]:
        """Genera paráfrasis sintéticas de una política usando un grafo de sinónimos local determinista."""
        paraphrases = []
        words = text.lower().strip().split()

        # Intentar usar NLTK wordnet si está disponible localmente
        nltk_synonyms = {}
        try:
            import nltk
            from nltk.corpus import wordnet

            for word in words:
                syns = []
                for syn in wordnet.synsets(word):
                    for lemma in syn.lemmas():
                        name = lemma.name().replace("_", " ")
                        if name != word and name not in syns:
                            syns.append(name)
                if syns:
                    nltk_synonyms[word] = syns[:3]
        except Exception:
            pass

        # Generar paráfrasis reemplazando palabras por sus sinónimos
        for idx, word in enumerate(words):
            clean_word = word.strip(".,;:!?()\"'")
            syns = nltk_synonyms.get(clean_word) or self.SYNONYM_MAP.get(clean_word)
            if syns:
                for syn in syns[:3]:
                    new_words = list(words)
                    new_words[idx] = word.replace(clean_word, syn)
                    paraphrases.append(" ".join(new_words))

        # Reestructuración simple de frases
        if len(words) > 3:
            if words[0] in ("never", "always", "prohibit"):
                paraphrases.append(" ".join(words[1:]) + f" is {words[0]}ed")

        unique_paraphrases = list(dict.fromkeys(p for p in paraphrases if p.strip()))
        return unique_paraphrases[:5]

    def query_similar_tokens(self, query_text: str, threshold: float) -> List[int]:
        """Consulta el KDTree en O(log V) para obtener IDs de tokens similares."""
        if self.vocab_embeddings is None or self.kd_tree is None:
            return []

        try:
            import math

            query_emb = np.asarray(self.embedding_service.encode(query_text), dtype=float)
            norm = np.linalg.norm(query_emb)
            if norm > 1e-12:
                query_emb /= norm

            # d = sqrt(2 * (1 - cosine_sim)) -> d <= sqrt(2 * (1 - threshold))
            r = math.sqrt(2.0 * max(0.0, 1.0 - threshold))

            indices = self.kd_tree.query_ball_point(query_emb, r)
            return [self.vocab_token_ids[idx] for idx in indices]
        except Exception as e:
            logger.warning(f"Error consultando KDTree: {e}")
            return []

    def get_w_bank_mask(self) -> Dict[int, Tuple[str, int]]:
        """
        Retorna la matriz W_bank compilada.

        Returns:
            Dict mapeando token_id → (hardness: str, priority: int)
        """
        return self.w_bank.copy()

    def get_forbidden_token_ids(self, hardness: Optional[str] = None) -> Set[int]:
        """
        Retorna conjunto de token_ids prohibidos, opcionalmente filtrados por dureza.

        Args:
            hardness: Filtrar por "hard" | "soft" | None (todos)

        Returns:
            Set de token_ids prohibidos
        """
        if hardness is None:
            return set(self.w_bank.keys())

        return {token_id for token_id, (h, _) in self.w_bank.items() if h == hardness}

    def get_compilation_report(self) -> Dict[str, Any]:
        """Retorna reporte detallado de compilación."""
        successful = sum(1 for r in self.compilation_log if r.compilation_status == "success")
        warnings = sum(1 for r in self.compilation_log if r.compilation_status == "warning")
        errors = sum(1 for r in self.compilation_log if r.compilation_status == "error")

        return {
            "total_policies": len(self.compilation_log),
            "successful": successful,
            "warnings": warnings,
            "errors": errors,
            "w_bank_size": len(self.w_bank),
            "unique_forbidden_tokens": len(self.w_bank),
            "compilation_log": [
                {
                    "policy_id": r.policy_id,
                    "status": r.compilation_status,
                    "tokens_count": len(r.forbidden_tokens),
                    "message": r.message,
                }
                for r in self.compilation_log
            ],
        }
