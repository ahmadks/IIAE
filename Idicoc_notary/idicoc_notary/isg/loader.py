from __future__ import annotations

import hashlib
import re
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple, Protocol
from dataclasses import dataclass
import numpy as np

from idicoc_notary.utils.logger import get_logger

logger = get_logger("isg.policy_loader")


class PolicyLoader(Protocol):
    """Interfaz para la carga de políticas externos al sistema."""

    def load_policies(self) -> List[Dict[str, Any]]:
        """
        Carga y devuelve una lista de diccionarios que representan políticas.
        Cada diccionario debe tener las claves requeridas por el PropertyGraph.
        """
        ...


class InlinePolicyLoader:
    """Cargador de políticas en memoria (ideal para pruebas o configuración hardcodeada)."""

    def __init__(self, policies: List[Dict[str, Any]]) -> None:
        self.policies = policies

    def load_policies(self) -> List[Dict[str, Any]]:
        return self.policies


def parse_policy_line(line: str, line_idx: int) -> Dict[str, Any]:
    # 1. Inferencia de Dureza
    hardness = "soft"
    if "[HARD]" in line.upper():
        hardness = "hard"
        line = re.sub(r"\[HARD\]", "", line, flags=re.IGNORECASE).strip()
    elif "[SOFT]" in line.upper():
        line = re.sub(r"\[SOFT\]", "", line, flags=re.IGNORECASE).strip()

    # 2. Detección / Inferencia de Tipo de Política y Patrón
    policy_type = "fact"
    pattern = None
    regex_match = re.search(r"\[REGEX:\s*(.*?)\s*\]", line, flags=re.IGNORECASE)
    if regex_match:
        policy_type = "regex"
        pattern = regex_match.group(1).strip()
        line = re.sub(r"\[REGEX:.*?\]", "", line, flags=re.IGNORECASE).strip()

    # 3. Inferencia de Polaridad
    polarity = "affirmative"
    if "[NEGATIVE]" in line.upper():
        polarity = "negative"
        line = re.sub(r"\[NEGATIVE\]", "", line, flags=re.IGNORECASE).strip()
    elif "[AFFIRMATIVE]" in line.upper():
        polarity = "affirmative"
        line = re.sub(r"\[AFFIRMATIVE\]", "", line, flags=re.IGNORECASE).strip()
    else:
        negation_pattern = re.compile(
            r"\b(no|evitar|evite|prohibido|prohíbe|prohibir|nunca|jamás|ni|sin|avoid|never|forbidden|reject|not)\b",
            re.IGNORECASE
        )
        if negation_pattern.search(line) or (policy_type == "regex" and not line.strip()):
            polarity = "negative"

    # 4. ID Determinista
    text_to_hash = line if line.strip() else (pattern or "")
    text_hash = hashlib.sha256(text_to_hash.encode("utf-8")).hexdigest()[:8]
    policy_id = f"free_text_{line_idx+1}_{text_hash}"

    policy = {
        "id": policy_id,
        "policy_id": policy_id,
        "text": line if line.strip() else (pattern or "Regex constraint"),
        "policy_type": policy_type,
        "polarity": polarity,
        "hardness": hardness,
        "priority": 1,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    if pattern:
        policy["pattern"] = pattern

    return policy


class FilePolicyLoader:
    """
    Cargador de políticas desde un archivo en lenguaje natural (texto libre) o JSON.
    """

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path

    def load_policies(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.file_path):
            logger.warning(f"Policy file not found: {self.file_path}. Returning empty list.")
            return []

        if self.file_path.endswith(".json"):
            return self._load_json()
        return self._load_text()

    def _load_json(self) -> List[Dict[str, Any]]:
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "policies" in data:
                    return data["policies"]
                return []
        except Exception as e:
            logger.error(f"Error reading JSON policy file {self.file_path}: {e}")
            return []

    def _load_text(self) -> List[Dict[str, Any]]:
        policies = []
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                for line_idx, line in enumerate(f):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    policies.append(self._parse_policy(line, line_idx))
        except Exception as e:
            logger.error(f"Error reading text policy file {self.file_path}: {e}")
        return policies

    def _parse_policy(self, line: str, line_idx: int) -> Dict[str, Any]:
        p = parse_policy_line(line, line_idx)
        p["source"] = f"file:{os.path.basename(self.file_path)}:{line_idx+1}"
        return p


@dataclass
class InvariantToken:
    """Representación de un token individual prohibido."""

    token_id: int
    token_text: str
    source_policy: str
    policy_id: Optional[str] = None
    hardness: str = "soft"
    priority: int = 1


@dataclass
class PolicyCompilationResult:
    """Resultado de la compilación de una política individual."""

    policy_id: Optional[str]
    policy_text: str
    forbidden_tokens: List[InvariantToken]
    compilation_status: str
    message: str


class InvariantSynthesizer:
    """
    Compilador determinista de políticas → W_bank.
    """

    def __init__(
        self,
        tokenizer: Any = None,
        embedding_service: Optional[Any] = None,
        embedding_threshold: float = 0.65,
        precompute_vocab_embeddings: bool = False,
        vocab_cache_path: Optional[str] = None,
    ) -> None:
        if tokenizer is None:
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
                "EmbeddingService es obligatorio para InvariantSynthesizer."
            )
        self.w_bank: Dict[int, Tuple[str, int]] = {}
        self.compilation_log: List[PolicyCompilationResult] = []
        self.vocab_size = len(tokenizer) if hasattr(tokenizer, "__len__") else tokenizer.vocab_size
        self.embedding_threshold = embedding_threshold
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

    def compile_policies(
        self,
        policies: List[Dict[str, Any]],
        include_variants: bool = True,
        hardness_multiplier: float = 1.0,
    ) -> Dict[int, Tuple[str, int]]:
        self.w_bank.clear()
        self.compilation_log.clear()

        hard_policies = sum(1 for p in policies if p.get("hardness") == "hard")
        soft_policies = len(policies) - hard_policies

        for policy in policies:
            result = self._compile_single_policy(
                policy,
                include_variants=include_variants,
                hardness_multiplier=hardness_multiplier,
            )
            self.compilation_log.append(result)

        return self.w_bank

    def _compile_single_policy(
        self,
        policy: Dict[str, Any],
        include_variants: bool = True,
        hardness_multiplier: float = 1.0,
    ) -> PolicyCompilationResult:
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
            base_tokens = self._extract_concept_tokens(policy_text, policy_id, hardness, priority)
            forbidden_tokens.extend(base_tokens)

            if include_variants and self.embedding_service:
                variant_tokens = self._generate_semantic_variants(
                    policy_text, policy_id, hardness, priority
                )
                forbidden_tokens.extend(variant_tokens)

            for token_info in forbidden_tokens:
                priority_scaled = token_info.priority
                if hardness == "hard":
                    priority_scaled = int(priority_scaled * hardness_multiplier)

                if token_info.token_id in self.w_bank:
                    existing_hardness, existing_priority = self.w_bank[token_info.token_id]
                    new_hardness = (
                        "hard" if hardness == "hard" or existing_hardness == "hard" else "soft"
                    )
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
        tokens: List[InvariantToken] = []

        try:
            similar_token_ids = self.query_similar_tokens(text, self.embedding_threshold)

            if not similar_token_ids:
                logger.warning(
                    f"[Ambiguity Alert] La política '{text[:50]}...' no generó un ancla vectorial fuerte."
                )
                return tokens

            for token_id in similar_token_ids[:50]:
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
        clean_tokens = [t.replace("Ġ", "").replace(" ", "") for t in tokens_text]

        try:
            embs = np.asarray(self.embedding_service.encode(clean_tokens), dtype=float)
        except TypeError:
            embs = np.asarray(
                self.embedding_service.encode(clean_tokens, convert_to_numpy=True), dtype=float
            )

        norms = np.linalg.norm(embs, axis=1, keepdims=True)
        norms = np.where(norms < 1e-12, 1.0, norms)
        embs = embs / norms

        self.vocab_tokens_text = tokens_text
        self.vocab_token_ids = token_ids
        self.vocab_embeddings = embs
        from scipy.spatial import KDTree

        self.kd_tree = KDTree(embs)

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
        variants: List[InvariantToken] = []

        if not self.embedding_service:
            return variants

        try:
            synthetic_variants = self._generate_synthetic_paraphrases(policy_text)

            seen_variant_ids: Set[int] = set()
            for variant in synthetic_variants:
                similar_ids = self.query_similar_tokens(variant, self.embedding_threshold)
                for token_id in similar_ids[:5]:
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
                            priority=max(1, priority - 1),
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
        paraphrases = []
        words = text.lower().strip().split()
        nltk_synonyms = {}

        for idx, word in enumerate(words):
            clean_word = word.strip(".,;:!?()\"'")
            syns = nltk_synonyms.get(clean_word) or self.SYNONYM_MAP.get(clean_word)
            if syns:
                for syn in syns[:3]:
                    new_words = list(words)
                    new_words[idx] = word.replace(clean_word, syn)
                    paraphrases.append(" ".join(new_words))

        if len(words) > 3:
            if words[0] in ("never", "always", "prohibit"):
                paraphrases.append(" ".join(words[1:]) + f" is {words[0]}ed")

        unique_paraphrases = list(dict.fromkeys(p for p in paraphrases if p.strip()))
        return unique_paraphrases[:5]

    def query_similar_tokens(self, query_text: str, threshold: float) -> List[int]:
        if self.vocab_embeddings is None or self.kd_tree is None:
            return []

        try:
            import math

            query_emb = np.asarray(self.embedding_service.encode(query_text), dtype=float)
            norm = np.linalg.norm(query_emb)
            if norm > 1e-12:
                query_emb /= norm

            r = math.sqrt(2.0 * max(0.0, 1.0 - threshold))

            indices = self.kd_tree.query_ball_point(query_emb, r)
            return [self.vocab_token_ids[idx] for idx in indices]
        except Exception as e:
            logger.warning(f"Error consultando KDTree: {e}")
            return []

    def get_w_bank_mask(self) -> Dict[int, Tuple[str, int]]:
        return self.w_bank.copy()

    def get_forbidden_token_ids(self, hardness: Optional[str] = None) -> Set[int]:
        if hardness is None:
            return set(self.w_bank.keys())

        return {token_id for token_id, (h, _) in self.w_bank.items() if h == hardness}

    def get_compilation_report(self) -> Dict[str, Any]:
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
