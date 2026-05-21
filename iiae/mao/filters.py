"""Language-agnostic lexical filters for the MAO forensic protocol (Annex V).

No locale or language configuration — token overlap and statistical proxies only.
ML/LLM engines in ``examples/mao/`` replace these heuristics per integration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Set


@dataclass
class MAOFilterConfig:
    """Thresholds for the lexical MAO fallback (model-agnostic)."""

    causality_threshold: float = 0.20
    min_word_len: int = 4
    axiom_preservation_threshold: float = 0.50
    borel_threshold: float = 0.05
    enable_stemming: bool = False


def _token_pattern(min_len: int) -> str:
    return rf"\b\w{{{min_len},}}\b"


def _stem_token(token: str) -> str:
    for suffix in ("ization", "isation", "ingly", "edly", "ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            return token[: -len(suffix)]
    return token


def _normalize_tokens(text: str, config: MAOFilterConfig) -> Set[str]:
    tokens = re.findall(_token_pattern(config.min_word_len), text.lower())
    if config.enable_stemming:
        return {_stem_token(t) for t in tokens}
    return set(tokens)


def material_causality_filter(
    response: str,
    rag_context: str,
    config: Optional[MAOFilterConfig] = None,
) -> dict:
    """V.1 — Material causality: grounding in material (RAG) context."""
    cfg = config or MAOFilterConfig()
    if not response or not rag_context:
        return {"passed": False, "score": None, "reason": "Empty execution bounds."}

    context_words = _normalize_tokens(rag_context, cfg)
    response_words = _normalize_tokens(response, cfg)
    if not response_words:
        return {"passed": True, "score": 1.0, "reason": None}

    overlap = response_words.intersection(context_words)
    score = len(overlap) / len(response_words)
    return {
        "passed": score >= cfg.causality_threshold,
        "score": round(score, 4),
        "reason": None,
    }


def axiomatic_invariance_filter(
    axioms: list,
    response: str,
    config: Optional[MAOFilterConfig] = None,
) -> dict:
    """V.3 — Literal operational preservation of axiom content (no data loss)."""
    cfg = config or MAOFilterConfig()
    if not axioms:
        return {"passed": True, "score": None, "reason": "No formal constraints defined."}

    response_tokens = _normalize_tokens(response, cfg)
    if not response_tokens:
        return {"passed": False, "score": 0.0, "reason": "Response has no operational tokens."}

    scores = []
    for ax in axioms:
        ax_tokens = _normalize_tokens(ax, cfg)
        if not ax_tokens:
            continue
        preserved = len(ax_tokens.intersection(response_tokens)) / len(ax_tokens)
        scores.append(preserved)

    if not scores:
        return {"passed": True, "score": 1.0, "reason": None}

    score = min(scores)
    return {
        "passed": score >= cfg.axiom_preservation_threshold,
        "score": round(score, 4),
        "reason": None if score >= cfg.axiom_preservation_threshold else "Axiomatic data loss detected.",
    }


def concurrent_probability_filter(
    response: str,
    rag_context: str,
    axioms: list,
    config: Optional[MAOFilterConfig] = None,
) -> dict:
    """V.2 — Borel limit: discard random-chance explanation when P is near zero."""
    cfg = config or MAOFilterConfig()
    causality = material_causality_filter(response, rag_context, cfg)
    c_score = causality.get("score") or 0.0

    ax_scores = []
    for ax in axioms or []:
        ax_rep = axiomatic_invariance_filter([ax], response, cfg)
        if ax_rep.get("score") is not None:
            ax_scores.append(ax_rep["score"])
    ax_mean = sum(ax_scores) / len(ax_scores) if ax_scores else 1.0

    # Combined improbability of random alignment (product of independent proxies).
    p_random = (1.0 - c_score) * (1.0 - ax_mean)
    p_random = max(0.0, min(1.0, p_random))

    return {
        "passed": p_random <= cfg.borel_threshold,
        "score": round(p_random, 6),
        "reason": None if p_random <= cfg.borel_threshold else "Alignment explainable as random chance.",
    }


def geoclimatic_synchrony_filter(
    response: str,
    rag_context: str,
) -> dict:
    """V.4 — Lexical stub; hardware footprint requires an ML-integrated engine."""
    return {
        "passed": True,
        "score": None,
        "reason": "Lexical engine defers hardware footprint validation to ML integration.",
    }

