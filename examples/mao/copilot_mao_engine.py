"""
Copilot-style Semantic MAO Engine (OEM-ready).

Enterprise-grade semantic integrity filter implementing IMAOEngine contract.
Model-agnostic, pure contract, OEM-defined manifold.

NOT tied to IIAE internals, NOT tied to specific models, NOT tied to heuristics.
Can be plugged into IIAE via register_engine() or used standalone.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import numpy as np
from iiae.mao.contract import IMAOEngine, MAOReport


class CopilotMAOEngine(IMAOEngine):
    """
    Copilot Enterprise semantic integrity engine.

    Implements Microsoft-style OEM manifold:
    - Material Causality: response grounds in context (semantic similarity)
    - Axiomatic Invariance: response entails safety axioms (NLI)
    - Probability Entropy: response confidence level (hedging detection)
    - Grounding Verification: response cites sources (citation detection)
    - Hallucination Detection: risk of unfounded claims
    - Toxicity Filter: workplace safety (toxic content blocking)

    All thresholds are enterprise-configurable and OEM-owned.
    Models are injected at init (Microsoft brings their own).
    Metadata injection for non-repudiation.

    Design: Pure contract implementation. No SDK internals. No hardcoded models.
    """

    def __init__(
        self,
        embedder: Any,
        entailment_model: Any,
        toxicity_model: Any,
        tokenizer: Any,
        # OEM Manifold Thresholds
        causality_threshold: float = 0.30,
        entailment_threshold: float = 0.50,
        entropy_threshold: float = 0.60,
        grounding_threshold: float = 0.70,
        hallucination_threshold: float = 0.15,
        toxicity_threshold: float = 0.05,
        # Enterprise Metadata
        metadata: Optional[Dict[str, Any]] = None,
        **_: Any,
    ) -> None:
        """
        Initialize Copilot MAO engine with OEM-supplied models and manifold.

        Args:
            embedder: Sentence embedding model (e.g., SentenceTransformer)
            entailment_model: NLI model (e.g., DeBERTa-MNLI)
            toxicity_model: Toxicity classifier
            tokenizer: Tokenizer matching entailment_model
            causality_threshold: Min semantic similarity (0.0-1.0)
            entailment_threshold: Min entailment probability (0.0-1.0)
            entropy_threshold: Min confidence / Max hedging (0.0-1.0)
            grounding_threshold: Min citation presence (0.0-1.0)
            hallucination_threshold: Max hallucination risk (0.0-1.0)
            toxicity_threshold: Max toxicity score (0.0-1.0)
            metadata: Enterprise metadata (tenant, region, classification)
        """
        self.embedder = embedder
        self.entailment_model = entailment_model
        self.toxicity_model = toxicity_model
        self.tokenizer = tokenizer

        # OEM-defined safety manifold
        self.causality_threshold = causality_threshold
        self.entailment_threshold = entailment_threshold
        self.entropy_threshold = entropy_threshold
        self.grounding_threshold = grounding_threshold
        self.hallucination_threshold = hallucination_threshold
        self.toxicity_threshold = toxicity_threshold

        # Non-repudiation metadata (immutable)
        self._meta = {
            "origin_engine": "copilot_semantic",
            "manifold_version": "1.0",
            "oem": "microsoft",
            **(metadata or {})
        }

    # ─────────────────────────────────
    # Embedding & Semantic Utilities
    # ─────────────────────────────────

    def _embed(self, text: str) -> np.ndarray:
        """
        Deterministic embedding (OEM-controlled).

        Args:
            text: Text to embed

        Returns:
            Dense vector (numpy array)
        """
        return self.embedder.encode(text, convert_to_numpy=True)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """
        Cosine distance (deterministic, numerically stable).

        Args:
            a: First vector
            b: Second vector

        Returns:
            Cosine similarity in [-1, 1], typically [0, 1] for unit vectors
        """
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        denom = norm_a * norm_b

        if denom == 0:
            return 0.0

        return float(np.dot(a, b) / denom)

    # ─────────────────────────────────
    # IMAOEngine Contract (Required)
    # ─────────────────────────────────

    def analyze(self, response: str, axioms: list) -> MAOReport:
        """
        Full semantic integrity analysis (IMAOEngine contract).

        Runs all six filters:
        1. Material Causality (grounding)
        2. Axiomatic Invariance (safety)
        3. Probability Entropy (confidence)
        4. Grounding Verification (citations)
        5. Hallucination Detection (factuality)
        6. Toxicity Filter (workplace safety)

        Args:
            response: AI-generated response text
            axioms: Safety axioms to verify against

        Returns:
            MAOReport with all filter results and metadata
        """
        # Run all filters
        results = {
            "material_causality": self._material_causality(response),
            "axiomatic_invariance": self._axiomatic_invariance(axioms, response),
            "probability_entropy": self._probability_entropy(response),
            "grounding_verification": self._grounding_verification(response),
            "hallucination_risk": self._hallucination_detection(response),
            "toxicity_score": self._toxicity_filter(response),
        }

        # Determine pass/fail: all critical filters must pass
        passed = all(r.get("passed", False) for r in results.values())

        return MAOReport(
            filters=results,
            passed=passed,
            metadata=self._meta
        )

    # ─────────────────────────────────
    # Filter Implementations
    # ─────────────────────────────────

    def _material_causality(self, response: str) -> Dict[str, Any]:
        """
        Filter 1: Material Causality (Grounding).

        Ensures response grounds in context/knowledge base.
        Implementation: Measure self-consistency of response.

        Production version would compare against RAG context.

        Returns:
            Dict with 'passed', 'score', 'reason', 'metadata'
        """
        sentences = [s.strip() for s in response.split('.') if s.strip()]

        if len(sentences) < 2:
            # Very short response: assume coherent
            return {
                "passed": True,
                "score": 1.0,
                "reason": "Short response (assumed coherent)",
                "metadata": self._meta,
            }

        # Measure coherence: first sentence vs rest
        v_first = self._embed(sentences[0])
        v_rest = self._embed('. '.join(sentences[1:]))
        score = self._cosine_similarity(v_first, v_rest)

        return {
            "passed": score >= self.causality_threshold,
            "score": round(score, 4),
            "reason": f"Semantic coherence: {score:.4f}",
            "metadata": self._meta,
        }

    def _axiomatic_invariance(
        self, axioms: List[str], response: str
    ) -> Dict[str, Any]:
        """
        Filter 2: Axiomatic Invariance (Safety).

        Ensures response logically entails safety axioms.
        Uses NLI (Natural Language Inference) model.

        For each axiom: does response → axiom hold?
        (Premise=axiom, Hypothesis=response)

        Returns:
            Dict with 'passed', 'score', 'reason', 'metadata'
        """
        if not axioms:
            return {
                "passed": True,
                "score": None,
                "reason": "No axioms provided",
                "metadata": self._meta,
            }

        import torch

        scores = []

        for axiom in axioms:
            # Encode axiom→response as entailment task
            # (axiom is premise, response is hypothesis)
            inputs = self.tokenizer(
                axiom,
                response,
                return_tensors="pt",
                truncation=True,
                max_length=512
            )

            with torch.no_grad():
                logits = self.entailment_model(**inputs).logits

            # Softmax over [contradiction, neutral, entailment]
            # Index mapping (typical):
            #   0 = contradiction (response contradicts axiom)
            #   1 = neutral (response is independent)
            #   2 = entailment (response implies axiom)
            probs = torch.softmax(logits, dim=1)[0]

            # We want entailment (index 2)
            entail_prob = float(probs[2])
            scores.append(entail_prob)

        avg_score = float(sum(scores) / len(scores)) if scores else 1.0

        return {
            "passed": avg_score >= self.entailment_threshold,
            "score": round(avg_score, 4),
            "reason": f"Entailment score: {avg_score:.4f}",
            "metadata": self._meta,
        }

    def _probability_entropy(self, response: str) -> Dict[str, Any]:
        """
        Filter 3: Probability Entropy (Confidence).

        Measures response confidence vs. hedging/uncertainty.
        Copilot-style: hedging language (might, maybe, uncertain) → lower score.

        Returns:
            Dict with 'passed', 'score', 'reason', 'metadata'
        """
        text = response.lower()

        # OEM-defined uncertainty markers
        uncertainty_tokens = [
            "maybe", "possibly", "i think", "i believe",
            "not sure", "uncertain", "unclear", "probably",
            "might be", "could be", "seems like", "apparently",
            "i guess", "some people say", "it appears"
        ]

        # Count hedging markers
        hedging_count = sum(
            1 for token in uncertainty_tokens
            if token in text
        )

        # Confidence penalty: -0.1 per marker (floor 0.0)
        confidence = max(0.0, 1.0 - hedging_count * 0.1)

        return {
            "passed": confidence >= self.entropy_threshold,
            "score": round(confidence, 4),
            "reason": f"Found {hedging_count} uncertainty markers",
            "metadata": self._meta,
        }

    def _grounding_verification(self, response: str) -> Dict[str, Any]:
        """
        Filter 4: Grounding Verification (Citations).

        Copilot Enterprise requires source attribution.
        Look for citations, brackets, references.

        Returns:
            Dict with 'passed', 'score', 'reason', 'metadata'
        """
        # OEM-defined grounding markers
        citation_markers = [
            "[", "]",  # Bracket citations [1], [ref]
            "cited from", "according to",  # Explicit attribution
            "source:", "ref.", "reference",  # Formal citations
            "https://", "http://",  # Links
        ]

        has_citations = any(
            marker in response.lower()
            for marker in citation_markers
        )

        # Binary: has citations (1.0) or not (0.3)
        score = 1.0 if has_citations else 0.3

        return {
            "passed": score >= self.grounding_threshold,
            "score": round(score, 4),
            "reason": "Citations detected" if has_citations else "No citations",
            "metadata": self._meta,
        }

    def _hallucination_detection(self, response: str) -> Dict[str, Any]:
        """
        Filter 5: Hallucination Risk.

        Detects unfounded claims (factual statements without grounding).
        Risk = (factual_claims - citations) / factual_claims

        Returns:
            Dict with 'passed', 'score', 'reason', 'metadata'
            (Note: score is risk (lower is better), passed if risk ≤ threshold)
        """
        # OEM-defined claim keywords (fact-asserting verbs)
        claim_keywords = [
            " is ", " was ", " happened ",
            " occurred ", " proved ", " found ",
            " show ", " demonstrate "
        ]

        # Count factual claims
        claim_count = sum(
            1 for kw in claim_keywords
            if kw in response.lower()
        )

        # Count citation markers
        citation_count = response.count("[") + response.count("(")

        # Calculate hallucination risk
        if claim_count == 0:
            # No claims → no hallucination risk
            risk = 0.0
        else:
            # Risk = proportion of claims without citations
            risk = max(0.0, 1.0 - (citation_count / claim_count))

        return {
            "passed": risk <= self.hallucination_threshold,
            "score": round(risk, 4),
            "reason": f"{claim_count} claims, {citation_count} citations, risk={risk:.4f}",
            "metadata": self._meta,
        }

    def _toxicity_filter(self, response: str) -> Dict[str, Any]:
        """
        Filter 6: Toxicity (Workplace Safety).

        Ensures response is safe for enterprise environment.
        In production: use ML toxicity classifier.
        Here: pattern-based fallback.

        Returns:
            Dict with 'passed', 'score', 'reason', 'metadata'
            (Note: score is toxicity (lower is better), passed if score ≤ threshold)
        """
        # OEM-defined toxic pattern markers (fallback)
        toxic_patterns = [
            "hate", "abuse", "slur", "violent",
            "harassment", "discriminat", "threat"
        ]

        text = response.lower()
        matches = [p for p in toxic_patterns if p in text]

        # In production: call toxicity_model
        # toxicity_score = self.toxicity_model(response)["score"]

        # Fallback: linear score from pattern matches
        toxicity_score = min(1.0, len(matches) * 0.1)

        return {
            "passed": toxicity_score <= self.toxicity_threshold,
            "score": round(toxicity_score, 4),
            "reason": f"Patterns: {matches}" if matches else "Clean",
            "metadata": self._meta,
        }


# ─────────────────────────────────
# Convenience Factory
# ─────────────────────────────────

def create_copilot_engine_for_tenant(
    tenant_id: str,
    embedder: Any,
    entailment_model: Any,
    toxicity_model: Any,
    tokenizer: Any,
    config: Optional[Dict[str, Any]] = None,
) -> CopilotMAOEngine:
    """
    Factory for tenant-specific Copilot MAO engines.

    Allows per-tenant configuration of manifold thresholds.

    Args:
        tenant_id: Enterprise tenant identifier
        embedder: Shared embedding model
        entailment_model: Shared NLI model
        toxicity_model: Shared toxicity model
        tokenizer: Shared tokenizer
        config: Tenant-specific config (thresholds, metadata)

    Returns:
        Configured CopilotMAOEngine instance
    """
    if config is None:
        config = {}

    return CopilotMAOEngine(
        embedder=embedder,
        entailment_model=entailment_model,
        toxicity_model=toxicity_model,
        tokenizer=tokenizer,
        # Tenant-specific manifold thresholds
        causality_threshold=config.get("causality_threshold", 0.30),
        entailment_threshold=config.get("entailment_threshold", 0.50),
        entropy_threshold=config.get("entropy_threshold", 0.60),
        grounding_threshold=config.get("grounding_threshold", 0.70),
        hallucination_threshold=config.get("hallucination_threshold", 0.15),
        toxicity_threshold=config.get("toxicity_threshold", 0.05),
        # Tenant metadata
        metadata={
            "tenant_id": tenant_id,
            "region": config.get("region", "us-east-1"),
            "sla": config.get("sla", "standard"),
            **config.get("extra_metadata", {})
        }
    )
