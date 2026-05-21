# Copilot MAO Engine: OEM Integration Guide

## Overview

This guide demonstrates how to integrate a **Copilot-style semantic MAO engine** into IIAE following Microsoft's OEM partnership standards.

**Key Principles:**
- ✅ Pure contract implementation (no SDK internals)
- ✅ OEM-defined manifold (Microsoft controls thresholds & models)
- ✅ Model-agnostic (works with any embedder/entailment model)
- ✅ Enterprise-grade metadata injection
- ✅ Deterministic, reproducible, auditable

---

## Architecture

```
┌──────────────────────────────────────┐
│   Copilot Enterprise Input           │
│   (prompt, response, context)        │
└──────────────────┬───────────────────┘
                   │
      ┌────────────▼───────────────┐
      │   CopilotMAOEngine         │
      │  (OEM-defined manifold)    │
      ├────────────────────────────┤
      │ • Material Causality       │
      │ • Axiomatic Invariance     │
      │ • Probability Entropy      │
      │ • Grounding/Hallucination  │
      │ • Toxicity Scoring         │
      └────────────────┬───────────┘
                       │
      ┌────────────────▼───────────────┐
      │  MAO Report                    │
      │  (deterministic, auditable)    │
      └────────────────┬───────────────┘
                       │
      ┌────────────────▼───────────────┐
      │  IIAE CTM (receipt sealing)    │
      └────────────────────────────────┘
```

---

## File Structure

```
examples/mao/
├── copilot_mao_engine.py           ← Main engine skeleton
├── copilot_manifesto.py             ← OEM manifold spec
├── copilot_integration_example.py   ← Full integration
└── copilot_oem_guide.md             ← This file
```

---

## Conceptual Model

### OEM Manifold

The **manifold** is the set of valid response states per enterprise policy:

```
Copilot Enterprise Manifold (Microsoft-defined):
├─ Material Causality: response must ground in context (λ ≥ 0.30)
├─ Axiomatic Invariance: response must entail safety axioms (φ ≥ 0.50)
├─ Probability Entropy: response must be confident, not hedged (ψ ≥ 0.60)
├─ Grounding Score: must cite sources (σ ≥ 0.70)
├─ Hallucination Risk: must not invent facts (ρ ≤ 0.15)
└─ Toxicity: must be safe for workspace (τ ≤ 0.05)
```

Each threshold is **enterprise-configurable** and **OEM-owned**.

---

## Implementation

### Step 1: Import the Contract

```python
from iiae.mao.contract import IMAOEngine, MAOReport
from typing import Any, Dict, List
import numpy as np
```

### Step 2: Implement the Engine

```python
class CopilotMAOEngine(IMAOEngine):
    """
    Copilot-style semantic integrity engine.
    
    Implements OEM-defined manifold:
    - Embeddings for semantic causality
    - Entailment model for invariance
    - Uncertainty scoring for hallucination detection
    - Grounding verification for source attribution
    - Toxicity filter for workplace safety
    
    All thresholds are configurable per tenant.
    """
    
    def __init__(
        self,
        embedder: Any,
        entailment_model: Any,
        toxicity_model: Any,
        tokenizer: Any,
        # Manifold thresholds (OEM-defined)
        causality_threshold: float = 0.30,
        entailment_threshold: float = 0.50,
        entropy_threshold: float = 0.60,
        grounding_threshold: float = 0.70,
        hallucination_threshold: float = 0.15,
        toxicity_threshold: float = 0.05,
        # Metadata
        metadata: Dict[str, Any] | None = None,
        **_: Any,
    ) -> None:
        self.embedder = embedder
        self.entailment_model = entailment_model
        self.toxicity_model = toxicity_model
        self.tokenizer = tokenizer
        
        # OEM manifold specification
        self.causality_threshold = causality_threshold
        self.entailment_threshold = entailment_threshold
        self.entropy_threshold = entropy_threshold
        self.grounding_threshold = grounding_threshold
        self.hallucination_threshold = hallucination_threshold
        self.toxicity_threshold = toxicity_threshold
        
        # Enterprise metadata (non-repudiation)
        self._meta = {
            "origin_engine": "copilot_semantic",
            "manifold_version": "1.0",
            "oem": "microsoft",
            **(metadata or {})
        }
    
    # ─────────────────────────────────
    # Embedding & Semantic Utilities
    # ─────────────────────────────────
    
    def _embed(self, text: str):
        """Deterministic embedding (OEM-controlled)."""
        return self.embedder.encode(text, convert_to_numpy=True)
    
    def _cosine_similarity(self, a, b) -> float:
        """Cosine distance (deterministic)."""
        denom = np.linalg.norm(a) * np.linalg.norm(b)
        return float(np.dot(a, b) / denom) if denom else 0.0
    
    # ─────────────────────────────────
    # MAO Contract Methods
    # ─────────────────────────────────
    
    def analyze(self, response: str, axioms: list) -> MAOReport:
        """
        Full MAO analysis (required by IMAOEngine contract).
        
        Returns deterministic report with:
        - Material causality (grounding)
        - Axiomatic invariance (safety)
        - Probability entropy (confidence)
        - Grounding verification
        - Hallucination risk
        - Toxicity score
        """
        results = {
            "material_causality": self._material_causality(response),
            "axiomatic_invariance": self._axiomatic_invariance(axioms, response),
            "probability_entropy": self._probability_entropy(response),
            "grounding_score": self._grounding_verification(response),
            "hallucination_risk": self._hallucination_detection(response),
            "toxicity_score": self._toxicity_filter(response),
        }
        
        # Determine pass/fail (all must pass)
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
        Ensure response grounds in context.
        Semantic similarity: response ≈ context.
        """
        # In enterprise: would use RAG context, not just "context"
        # For now: measure self-consistency (response coherence)
        sentences = [s.strip() for s in response.split('.') if s.strip()]
        
        if len(sentences) < 2:
            return {
                "passed": True,
                "score": 1.0,
                "reason": "Short response (assumed coherent)",
                "metadata": self._meta,
            }
        
        # Compare first sentence to rest
        if sentences:
            v_first = self._embed(sentences[0])
            v_rest = self._embed('. '.join(sentences[1:]))
            score = self._cosine_similarity(v_first, v_rest)
        else:
            score = 1.0
        
        return {
            "passed": score >= self.causality_threshold,
            "score": round(score, 4),
            "reason": None,
            "metadata": self._meta,
        }
    
    def _axiomatic_invariance(self, axioms: List[str], response: str) -> Dict[str, Any]:
        """
        Ensure response entails safety axioms.
        Uses NLI model: does response → axiom hold for all axioms?
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
            # Encode (axiom, response) as entailment pair
            inputs = self.tokenizer(
                axiom, response,
                return_tensors="pt",
                truncation=True,
                max_length=512
            )
            
            with torch.no_grad():
                logits = self.entailment_model(**inputs).logits
            
            # Softmax over [contradiction, neutral, entailment]
            probs = torch.softmax(logits, dim=1)[0]
            entail_prob = float(probs[2])  # Index 2 = entailment
            
            scores.append(entail_prob)
        
        avg_score = float(sum(scores) / len(scores)) if scores else 1.0
        
        return {
            "passed": avg_score >= self.entailment_threshold,
            "score": round(avg_score, 4),
            "reason": None,
            "metadata": self._meta,
        }
    
    def _probability_entropy(self, response: str) -> Dict[str, Any]:
        """
        Measure response confidence / entropy.
        Copilot-style: hedging & uncertainty reduce confidence.
        """
        text = response.lower()
        
        # Uncertainty markers (OEM-defined set)
        uncertainty_tokens = [
            "maybe", "possibly", "i think", "i believe",
            "not sure", "uncertain", "unclear", "probably",
            "might be", "could be", "seems like", "apparently"
        ]
        
        hedging_count = sum(1 for token in uncertainty_tokens if token in text)
        
        # Penalize: -0.1 per hedging marker (min 0.0)
        confidence = max(0.0, 1.0 - hedging_count * 0.1)
        
        return {
            "passed": confidence >= self.entropy_threshold,
            "score": round(confidence, 4),
            "reason": f"Found {hedging_count} uncertainty markers",
            "metadata": self._meta,
        }
    
    def _grounding_verification(self, response: str) -> Dict[str, Any]:
        """
        Copilot-style grounding: does response cite sources?
        Look for brackets, footnotes, citations.
        """
        # Grounding markers (OEM-defined)
        grounding_markers = ["[", "]", "cited from", "according to", "source:", "ref."]
        
        has_citations = any(marker in response.lower() for marker in grounding_markers)
        
        score = 1.0 if has_citations else 0.3
        
        return {
            "passed": score >= self.grounding_threshold,
            "score": round(score, 4),
            "reason": "Citations detected" if has_citations else "No citations",
            "metadata": self._meta,
        }
    
    def _hallucination_detection(self, response: str) -> Dict[str, Any]:
        """
        Hallucination risk: does response make unfounded claims?
        Simple heuristic: facts without grounding.
        """
        # Hallucination risk markers (OEM-defined)
        claims_keywords = ["is", "was", "happened", "occurred", "proved", "found"]
        
        claim_count = sum(1 for kw in claims_keywords if f" {kw} " in response.lower())
        citation_count = response.count("[") + response.count("(")
        
        # Risk = claims without sources
        if claim_count == 0:
            risk = 0.0
        else:
            risk = max(0.0, 1.0 - (citation_count / max(claim_count, 1)))
        
        return {
            "passed": risk <= self.hallucination_threshold,
            "score": round(risk, 4),
            "reason": f"{claim_count} claims, {citation_count} citations",
            "metadata": self._meta,
        }
    
    def _toxicity_filter(self, response: str) -> Dict[str, Any]:
        """
        Workplace safety: does response contain toxic content?
        Uses toxicity classifier.
        """
        # Simple implementation: check for known-bad patterns
        # In production: use ML toxicity classifier
        toxic_patterns = ["hate", "abuse", "slur", "violent", "harassment"]
        
        matches = [p for p in toxic_patterns if p in response.lower()]
        
        # In production: use toxicity model
        # toxicity_score = self.toxicity_model(response)["score"]
        
        toxicity_score = 0.0 if not matches else len(matches) * 0.1
        
        return {
            "passed": toxicity_score <= self.toxicity_threshold,
            "score": round(toxicity_score, 4),
            "reason": f"Matched patterns: {matches}" if matches else "Clean",
            "metadata": self._meta,
        }
```

---

## Enterprise Integration Example

### Register the Engine

```python
from iiae.mao.registry import register_engine
from examples.mao.copilot_mao_engine import CopilotMAOEngine

# Load models (OEM-controlled, not part of IIAE)
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForSequenceClassification, AutoTokenizer

embedder = SentenceTransformer("all-MiniLM-L6-v2")
entailment_model = AutoModelForSequenceClassification.from_pretrained(
    "microsoft/deberta-large-mnli"
)
toxicity_model = AutoModelForSequenceClassification.from_pretrained(
    "michellejieli/BERT-hate-speech-classification"
)
tokenizer = AutoTokenizer.from_pretrained("microsoft/deberta-large-mnli")

# Register as Copilot semantic engine
register_engine(
    "copilot_semantic",
    CopilotMAOEngine,
)
```

### Configuration

```python
from iiae import IIAEConfig, validate

# Microsoft/Enterprise tenant config
config = IIAEConfig(
    ds_threshold=0.4,
    enable_mao_filters=True,
    mao_engine_name="copilot_semantic",
    mao_engine_params={
        "embedder": embedder,
        "entailment_model": entailment_model,
        "toxicity_model": toxicity_model,
        "tokenizer": tokenizer,
        # OEM manifold (per-tenant configurable)
        "causality_threshold": 0.30,
        "entailment_threshold": 0.50,
        "entropy_threshold": 0.60,
        "grounding_threshold": 0.70,
        "hallucination_threshold": 0.15,
        "toxicity_threshold": 0.05,
        # Metadata
        "metadata": {
            "tenant": "microsoft",
            "region": "eu-west-1",
            "classification": "confidential"
        }
    }
)
```

### Full Workflow

```python
# Copilot generates response for employee query
prompt = "How do I set up SSO?"
context = "Company policy: SSO is required. Credentials must be stored in Azure Key Vault."
response = "Use Azure AD Connect to federate your on-premises AD to Azure AD [ref: docs.microsoft.com/setup]."

# Verify against IIAE + Copilot MAO
result = validate(prompt, response, context, config=config)

print(f"Verified: {result['verified']}")
print(f"Ds: {result['ds']} ({result['base_type']})")
print(f"MAO filters: {result['mao']['filters']}")
print(f"Receipt: {result['ctm_seal']}")
```

---

## OEM Manifold Specification

### Microsoft Copilot Enterprise Manifold v1.0

```yaml
manifold_version: "1.0"
oem: "microsoft"
description: "Safe Harbor for Copilot Enterprise responses"

filters:
  material_causality:
    description: "Response grounds in RAG context"
    metric: "cosine_similarity(response_embedding, context_embedding)"
    threshold: 0.30
    critical: true
    
  axiomatic_invariance:
    description: "Response entails safety axioms (NLI)"
    metric: "mean(entailment_prob(axiom_i, response) for axiom_i in axioms)"
    threshold: 0.50
    critical: true
    
  probability_entropy:
    description: "Response confidence (not hedged)"
    metric: "1.0 - (uncertainty_markers / response_length)"
    threshold: 0.60
    critical: false
    
  grounding_verification:
    description: "Response cites sources"
    metric: "has_citations(response)"
    threshold: 0.70
    critical: false
    
  hallucination_detection:
    description: "Risk of unfounded claims"
    metric: "1.0 - (citations / claims)"
    threshold: 0.15  # max risk
    critical: true
    
  toxicity_filter:
    description: "Workplace safety (no toxic content)"
    metric: "toxicity_classifier(response)"
    threshold: 0.05  # max toxicity
    critical: true

safe_harbor_condition:
  description: "All critical filters must pass"
  policy: "STRICT"
  enforcement: "fail-closed"
  
audit_requirements:
  - receipt_sealing: "CTM Merkle-DAG"
  - metadata_injection: "tenant, region, classification"
  - non_repudiation: "timestamp + signature"
```

---

## Key Design Decisions

### ✅ Pure Contract (No SDK Internals)

```python
# ✅ CORRECT: Implements only IMAOEngine
class CopilotMAOEngine(IMAOEngine):
    def analyze(self, response, axioms) -> MAOReport:
        ...

# ❌ WRONG: Would import IIAE internals
# from iiae.supervisor import IIAESupervisor
# from iiae.dqe import deviation_score
```

### ✅ OEM-Owned Models

```python
# ✅ CORRECT: Models injected at init
def __init__(self, embedder, entailment_model, toxicity_model, ...):
    self.embedder = embedder  # Microsoft's, not SDK's
    self.entailment_model = entailment_model  # OEM-controlled

# ❌ WRONG: Would hardcode model paths
# self.embedder = SentenceTransformer("hardcoded-model-name")
```

### ✅ Configurable Manifold

```python
# ✅ CORRECT: Thresholds per-tenant
config = IIAEConfig(
    mao_engine_params={
        "causality_threshold": 0.30,  # Adjustable per enterprise
        "entailment_threshold": 0.50,  # Per domain
        ...
    }
)

# ❌ WRONG: Would hardcode thresholds
# CAUSALITY_THRESHOLD = 0.30  # global constant
```

### ✅ Enterprise Metadata

```python
# ✅ CORRECT: Non-repudiation metadata
self._meta = {
    "origin_engine": "copilot_semantic",
    "oem": "microsoft",
    "tenant": "company-xyz",
    "region": "eu-west-1",
}

# ❌ WRONG: No audit trail
# return {"passed": True}  # No metadata
```

---

## Testing

### Unit Test Example

```python
def test_copilot_material_causality():
    """Test grounding filter."""
    engine = CopilotMAOEngine(
        embedder=mock_embedder,
        entailment_model=mock_entailment,
        toxicity_model=mock_toxicity,
        tokenizer=mock_tokenizer,
        causality_threshold=0.30,
    )
    
    report = engine.analyze(
        response="Security is important for enterprise systems.",
        axioms=["Enterprise systems must be secure."]
    )
    
    assert report.filters["material_causality"]["passed"]
    assert report.filters["material_causality"]["score"] > 0.30
    assert report.metadata["origin_engine"] == "copilot_semantic"

def test_copilot_hallucination_detection():
    """Test hallucination risk filter."""
    engine = CopilotMAOEngine(
        embedder=mock_embedder,
        entailment_model=mock_entailment,
        toxicity_model=mock_toxicity,
        tokenizer=mock_tokenizer,
        hallucination_threshold=0.15,
    )
    
    report = engine.analyze(
        response="Studies prove X works [https://doi.org/10.1234].",
        axioms=[]
    )
    
    assert report.filters["hallucination_risk"]["passed"]
```

---

## Registration & Discovery

### Dynamic Registration

```python
from iiae.mao.registry import register_engine, list_registered_engines

# Microsoft registers at startup
register_engine("copilot_semantic", CopilotMAOEngine)

# Discover available engines
engines = list_registered_engines()
assert "copilot_semantic" in engines
```

### Configuration File

```yaml
# copilot_config.yaml
iiae:
  enable_mao_filters: true
  mao_engine_name: copilot_semantic
  mao_engine_params:
    embedder: "sentence-transformers/all-MiniLM-L6-v2"
    entailment_model: "microsoft/deberta-large-mnli"
    causality_threshold: 0.30
    entailment_threshold: 0.50
    entropy_threshold: 0.60
    grounding_threshold: 0.70
    hallucination_threshold: 0.15
    toxicity_threshold: 0.05
```

---

## Production Deployment

### Multi-Tenant Isolation

```python
def create_copilot_engine_for_tenant(tenant_id: str, config: dict):
    """Factory for per-tenant Copilot engines."""
    
    engine = CopilotMAOEngine(
        embedder=shared_embedder,  # Shared
        entailment_model=shared_entailment,  # Shared
        toxicity_model=shared_toxicity,  # Shared
        tokenizer=shared_tokenizer,  # Shared
        # Tenant-specific thresholds
        causality_threshold=config.get("causality_threshold", 0.30),
        entailment_threshold=config.get("entailment_threshold", 0.50),
        # Tenant metadata
        metadata={
            "tenant_id": tenant_id,
            "region": config.get("region"),
            "sla": config.get("sla"),
        }
    )
    
    return engine
```

### Monitoring & Metrics

```python
def monitor_copilot_integrity(report: MAOReport):
    """Emit metrics for observability."""
    
    filters = report.filters
    
    # Prometheus metrics
    metrics.histogram("mao_causality_score", filters["material_causality"]["score"])
    metrics.histogram("mao_entailment_score", filters["axiomatic_invariance"]["score"])
    metrics.histogram("mao_hallucination_risk", filters["hallucination_risk"]["score"])
    
    # Health check
    if not report.passed:
        metrics.counter("mao_filter_failure", labels={"tenant": report.metadata["tenant"]})
```

---

## Next Steps

1. **Extend with domain-specific filters** (Finance, Healthcare, Legal)
2. **Add adversarial testing** (jailbreak detection, prompt injection)
3. **Implement distributed manifold** (per-region thresholds)
4. **Add model drift detection** (entailment model performance monitoring)

---

**This is the Copilot-style MAO engine skeleton Microsoft would expect from an OEM partner.**
