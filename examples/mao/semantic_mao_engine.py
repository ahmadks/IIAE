"""ML-integrated MAO engine (Annex V) — uses existing iiae_demo model loaders.

Requires::

    pip install 'iiae[core]'
    python download_models.py   # optional pre-cache for Streamlit Cloud
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from iiae.mao.contract import IMAOEngine
from iiae.mao.report import enrich_report

ORIGIN_ENGINE = "example_semantic"


class ExampleSemanticMAOEngine(IMAOEngine):
    """Annex V MAO via ``MiniRAG`` (embeddings) + ``EntailmentModel`` (NLI)."""

    def __init__(
        self,
        embed_model_path: Optional[str] = None,
        entail_model_path: Optional[str] = None,
        causality_threshold: float = 0.30,
        entailment_threshold: float = 0.50,
        borel_threshold: float = 0.05,
        geoclimatic_threshold: float = 0.25,
        **_: Any,
    ) -> None:
        from iiae_demo.entailment import EntailmentModel
        from iiae_demo.rag import MiniRAG

        self._embed_name = embed_model_path or "sentence-transformers/all-MiniLM-L6-v2"
        self._entail_name = entail_model_path or "cross-encoder/nli-deberta-v3-small"

        self._rag = MiniRAG(model_name=self._embed_name)
        self.embedder = self._rag.model
        self._entail = EntailmentModel(model_name=self._entail_name)
        self.tokenizer = self._entail.tokenizer
        self.entail_model = self._entail.model

        import numpy as np
        import torch

        self._np = np
        self._torch = torch
        self.causality_threshold = causality_threshold
        self.entailment_threshold = entailment_threshold
        self.borel_threshold = borel_threshold
        self.geoclimatic_threshold = geoclimatic_threshold

    def _trace(self, report: dict, filter_name: str) -> Dict[str, Any]:
        return enrich_report(
            report,
            origin_engine=ORIGIN_ENGINE,
            model=self._embed_name,
            entailment_model=self._entail_name,
            filter=filter_name,
        )

    def evaluate_boundaries(self, response: str, graph: any) -> Dict[str, Any]:
        results = {
            "material_causality": self.material_causality(response, graph.source_text),
            "probability_entropy": self.probability_entropy(
                response, graph.source_text, graph.axioms
            ),
            "axiomatic_invariance": self.axiomatic_invariance(graph.axioms, response),
            "geoclimatic_synchrony": self.geoclimatic_synchrony(response, graph.source_text),
        }
        passed = all(r.get("passed", False) for r in results.values())
        results["passed"] = passed
        if not passed:
            results["reason"] = "manifold boundary violation"
        return results

    def _embed(self, text: str):
        return self.embedder.encode(text, convert_to_numpy=True)

    def _cosine(self, a, b) -> float:
        denom = self._np.linalg.norm(a) * self._np.linalg.norm(b)
        return float(self._np.dot(a, b) / denom) if denom else 0.0

    def material_causality(self, response: str, rag_context: str) -> Dict[str, Any]:
        score = self._cosine(self._embed(response), self._embed(rag_context))
        return self._trace(
            {
                "passed": score > self.causality_threshold,
                "score": round(score, 4),
                "reason": None,
            },
            "material_causality",
        )

    def concurrent_probability(
        self, response: str, rag_context: str, axioms: List[str]
    ) -> Dict[str, Any]:
        causality = self.material_causality(response, rag_context)
        c_score = causality.get("score") or 0.0
        ax_scores = []
        for ax in axioms or []:
            rep = self.axiomatic_invariance([ax], response)
            if rep.get("score") is not None:
                ax_scores.append(rep["score"])
        ax_mean = sum(ax_scores) / len(ax_scores) if ax_scores else 1.0
        p_random = max(0.0, min(1.0, (1.0 - c_score) * (1.0 - ax_mean)))
        return self._trace(
            {
                "passed": p_random <= self.borel_threshold,
                "score": round(p_random, 6),
                "reason": None,
            },
            "probability_entropy",
        )

    def probability_entropy(
        self,
        response: str,
        rag_context: Optional[str] = None,
        axioms: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        return self.concurrent_probability(
            response, rag_context or "", axioms or []
        )

    def axiomatic_invariance(self, axioms: List[str], response: str) -> Dict[str, Any]:
        if not axioms:
            return self._trace(
                {"passed": True, "score": None, "reason": None},
                "axiomatic_invariance",
            )

        scores = []
        for ax in axioms:
            inputs = self.tokenizer(ax, response, return_tensors="pt", truncation=True)
            logits = self.entail_model(**inputs).logits
            entail_prob = self._torch.softmax(logits, dim=1)[0][1].item()
            scores.append(entail_prob)

        avg = float(sum(scores) / len(scores))
        return self._trace(
            {
                "passed": avg > self.entailment_threshold,
                "score": round(avg, 4),
                "reason": None,
            },
            "axiomatic_invariance",
        )

    def geoclimatic_synchrony(self, response: str, rag_context: str) -> Dict[str, Any]:
        score = self._cosine(self._embed(response), self._embed(rag_context))
        return self._trace(
            {
                "passed": score > self.geoclimatic_threshold,
                "score": round(score, 4),
                "reason": None,
            },
            "geoclimatic_synchrony",
        )
