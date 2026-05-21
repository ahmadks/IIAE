# Semantic Manifold Specification (Universal for All Commercial AI)

**Version:** 2.1  
**Last Updated:** May 2026  
**Target Audience:** AI integrators, ML engineers, domain specialists  
**Platforms Supported:** OpenAI, Azure OpenAI, Anthropic Claude, Google Gemini, Amazon Bedrock, Cohere, Mistral, and any commercial AI system

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [What is a Semantic Manifold?](#what-is-a-semantic-manifold)
3. [Design Principles](#design-principles)
4. [Core Interface](#core-interface)
5. [Filter Implementations](#filter-implementations)
6. [Manifold Types](#manifold-types)
7. [Integration with IIAE](#integration-with-iiae)
8. [Examples](#examples)
9. [Compliance Considerations](#compliance-considerations)

---

## Executive Summary

A **semantic manifold** is a vendor-neutral extension to IIAE's core verification layer. It allows any organization to:

- ✅ Define domain-specific verification rules (works with any AI model)
- ✅ Implement custom semantic filters (model-agnostic)
- ✅ Enforce industry regulations (same across all vendors)
- ✅ Create audit-trail evidence (portable to any AI vendor)
- ✅ Verify AI responses against proprietary policies (independent of AI provider)

**Key Benefit:** Your manifold works identically whether you use OpenAI, Azure OpenAI, Anthropic Claude, Google Gemini, Amazon Bedrock, or any other commercial AI system. Switch vendors without changing your verification code.

---

## What is a Semantic Manifold? (Universal Across All AI Systems)

### Simple Concept

A semantic manifold is a set of **four vendor-neutral verification filters**. They work the same whether your AI comes from OpenAI, Azure, Anthropic, Google, or any other provider:

Every commercial AI platform must have:

| Filter | Purpose | Universal? |
|--------|---------|------------|
| **Material Causality** | Verify response is grounded in facts | ✅ Works with any AI |
| **Axiomatic Invariance** | Verify response doesn't violate rules | ✅ Works with any AI |
| **Geoclimatic Synchrony** | Verify response is contextually aligned | ✅ Works with any AI |
| **Probability Entropy** | Verify response shows appropriate confidence | ✅ Works with any AI |

### Architecture

```
┌─────────────────────────────────────────────┐
│         Your Semantic Manifold              │
│         (OEM-defined verification layer)    │
├─────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────┐ │
│ │ Material Causality                      │ │
│ │ (groundedness in facts)                 │ │
│ └─────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────┐ │
│ │ Axiomatic Invariance                    │ │
│ │ (policy compliance)                     │ │
│ └─────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────┐ │
│ │ Geoclimatic Synchrony                   │ │
│ │ (context alignment)                     │ │
│ └─────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────┐ │
│ │ Probability Entropy                     │ │
│ │ (confidence calibration)                │ │
│ └─────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
         │
         ↓
   ┌─────────────┐
   │ IIAE Core   │
   │ (DQE, CTM)  │
   └─────────────┘
```

---

## Design Principles

### Principle 1: Vendor-Agnostic

Your manifold doesn't know or care which AI system generated the response.

```python
# This works the SAME regardless of which AI produced the response:

# OpenAI:
response = openai.ChatCompletion.create(...)

# Azure OpenAI:
response = azure_client.chat.completions.create(...)

# Anthropic Claude:
response = anthropic_client.messages.create(...)

# Google Gemini:
response = gemini_client.generate_content(...)

# Your verification layer:
result = validate(response, context)  # <- Works identically for all

### Principle 2: Deterministic
Each filter returns a **numeric score** (0.0 = fail, 1.0 = pass). Scoring must be reproducible.

```python
def material_causality(self, response: str, context: str) -> dict:
    # Must return same score for same inputs
    score = calculate_groundedness(response, context)  # Deterministic
    return {"passed": score > 0.5, "score": score, "metadata": {...}}
```

### Principle 3: Auditable
Every decision leaves a trace. Scores, checks, and metadata are logged.

```python
return {
    "passed": True,
    "score": 0.92,
    "metadata": {
        "origin_engine": "my_manifold",
        "check_type": "material_causality",
        "evidence": ["fact_1", "fact_2"],
        "timestamp": "2026-05-21T10:30:00Z"
    }
}
```

### Principle 4: Composable
Multiple manifolds can run in parallel. Each adds its evidence to the audit trail.

```python
# IIAE can run:
result = validate(
    prompt=query,
    response=response,
    context=context,
    config=IIAEConfig(
        mao_engine_name="my_manifold"  # Your manifold
    )
)
```

### Principle 5: Non-blocking
A manifold failure should **not crash** the system. It should be logged and escalated.

```python
try:
    result = my_filter(response, context)
except Exception as e:
    # Log, but don't crash
    return {
        "passed": False,
        "error": str(e),
        "metadata": {"error_type": "filter_exception"}
    }
```

---

## Core Interface

Every semantic manifold must implement the `IMAOEngine` interface:

```python
from iiae.mao import IMAOEngine

class YourManifold(IMAOEngine):
    """Your OEM semantic manifold."""
    
    def material_causality(
        self, 
        response: str, 
        rag_context: str
    ) -> dict:
        """
        Verify response is grounded in RAG context.
        
        Args:
            response: AI model's response
            rag_context: Retrieved context from RAG
        
        Returns:
            {
                "passed": bool,
                "score": float (0.0 to 1.0),
                "metadata": dict
            }
        """
        pass
    
    def axiomatic_invariance(
        self, 
        axioms: list, 
        response: str
    ) -> dict:
        """
        Verify response doesn't violate business axioms.
        
        Args:
            axioms: List of business rules (extracted from context)
            response: AI model's response
        
        Returns:
            {
                "passed": bool,
                "score": float (0.0 to 1.0),
                "metadata": dict
            }
        """
        pass
    
    def geoclimatic_synchrony(
        self, 
        response: str, 
        rag_context: str
    ) -> dict:
        """
        Verify response is contextually synchronized.
        
        Args:
            response: AI model's response
            rag_context: Retrieved context
        
        Returns:
            {
                "passed": bool,
                "score": float (0.0 to 1.0),
                "metadata": dict
            }
        """
        pass
    
    def probability_entropy(
        self, 
        response: str
    ) -> dict:
        """
        Verify confidence is appropriately calibrated.
        
        Args:
            response: AI model's response
        
        Returns:
            {
                "passed": bool,
                "score": float (0.0 to 1.0),
                "metadata": dict
            }
        """
        pass
```

---

## Filter Implementations

### Filter 1: Material Causality

**Purpose:** Verify the response is grounded in facts (not hallucinated).

**Implementation Strategy:**

```python
def material_causality(self, response: str, rag_context: str) -> dict:
    """
    Check if response facts are mentioned in RAG context.
    
    Scoring:
    - 1.0: All key facts are in context
    - 0.5: Some facts are in context, some are new
    - 0.0: No facts are grounded in context
    """
    
    # Extract key entities/claims from response
    response_facts = extract_facts(response)
    context_facts = extract_facts(rag_context)
    
    # Calculate grounding ratio
    grounded = sum(1 for fact in response_facts 
                   if fact in context_facts)
    
    if not response_facts:
        score = 1.0  # No claims = grounded
    else:
        score = grounded / len(response_facts)
    
    return {
        "passed": score > 0.7,  # 70% of facts must be grounded
        "score": score,
        "metadata": {
            "grounded_facts": grounded,
            "total_facts": len(response_facts),
            "hallucination_risk": 1.0 - score
        }
    }
```

### Filter 2: Axiomatic Invariance

**Purpose:** Verify the response doesn't violate business rules (axioms).

**Implementation Strategy:**

```python
def axiomatic_invariance(self, axioms: list, response: str) -> dict:
    """
    Check if response violates any business axioms.
    
    Axioms are extracted from business rules/policies.
    Example axioms:
    - "Credit limit must not exceed $1M"
    - "Customer data must be encrypted"
    - "PII must never be logged"
    """
    
    violations = []
    
    for axiom in axioms:
        # Parse axiom (example: "X must [verb] Y")
        if is_violated(axiom, response):
            violations.append(axiom)
    
    if not axioms:
        score = 1.0
    else:
        score = 1.0 - (len(violations) / len(axioms))
    
    return {
        "passed": len(violations) == 0,
        "score": max(score, 0.0),
        "metadata": {
            "violations": violations,
            "violation_count": len(violations)
        }
    }
```

### Filter 3: Geoclimatic Synchrony

**Purpose:** Verify response is contextually aligned and relevant.

**Implementation Strategy:**

```python
def geoclimatic_synchrony(self, response: str, rag_context: str) -> dict:
    """
    Check if response is synchronized with context.
    
    Measures:
    - Is the response on-topic?
    - Does it address the actual question?
    - Is it contextually appropriate?
    """
    
    # Compute semantic similarity
    similarity = cosine_similarity(
        embed(response),
        embed(rag_context)
    )
    
    # Check temporal alignment (if applicable)
    response_time = extract_timestamp(response)
    context_time = extract_timestamp(rag_context)
    temporal_alignment = check_time_match(response_time, context_time)
    
    # Combined score
    score = (similarity * 0.7) + (temporal_alignment * 0.3)
    
    return {
        "passed": score > 0.5,
        "score": score,
        "metadata": {
            "semantic_similarity": similarity,
            "temporal_alignment": temporal_alignment,
            "synchrony_index": score
        }
    }
```

### Filter 4: Probability Entropy

**Purpose:** Verify the AI is appropriately confident or uncertain.

**Implementation Strategy:**

```python
def probability_entropy(self, response: str) -> dict:
    """
    Check if AI expresses appropriate confidence.
    
    Too certain: "Definitely..." "100% sure..."
    Too uncertain: "Maybe..." "Possibly..." "Might..."
    Just right: Matches the actual confidence level
    """
    
    # Count confidence indicators
    high_confidence_words = ["definitely", "certainly", "must", "always"]
    low_confidence_words = ["maybe", "possibly", "might", "could"]
    
    high_count = sum(1 for word in high_confidence_words 
                     if word in response.lower())
    low_count = sum(1 for word in low_confidence_words 
                    if word in response.lower())
    
    # Calculate entropy (confidence calibration)
    total_indicators = high_count + low_count
    
    if total_indicators == 0:
        # No explicit confidence indicators = neutral
        entropy = 0.5
    else:
        # Imbalance indicates over/under-confidence
        confidence_ratio = high_count / total_indicators
        entropy = 1.0 - abs(confidence_ratio - 0.5) * 2
    
    return {
        "passed": entropy > 0.4,  # Allow some variation
        "score": entropy,
        "metadata": {
            "high_confidence_indicators": high_count,
            "low_confidence_indicators": low_count,
            "entropy": entropy
        }
    }
```

---

## Manifold Types

### Type 1: Regulatory Compliance Manifold (Universal)

**Use Case:** Financial services, healthcare, government (works with any AI vendor)
**Focus:** Enforce regulatory requirements (GDPR, HIPAA, SOX, Basel III)

```python
class RegulatoryManifold(IMAOEngine):
    """Enforce regulatory compliance.
    
    Works with OpenAI, Azure, Claude, Gemini, Bedrock, Cohere,
    Mistral, or any other AI model.
    """
    
    def __init__(self, regulations: list):
        self.regulations = regulations  # ["GDPR", "HIPAA", "SOX"]
    
    def axiomatic_invariance(self, axioms: list, response: str) -> dict:
        # Check for regulatory violations
        for regulation in self.regulations:
            if violates_regulation(response, regulation):
                return {
                    "passed": False,
                    "score": 0.0,
                    "metadata": {"violation": regulation}
                }
        return {"passed": True, "score": 1.0, "metadata": {}}
```

### Type 2: Domain Expertise Manifold (Universal)

**Use Case:** Medical AI, financial analysis, scientific research (works with any AI vendor)
**Focus:** Verify domain-specific accuracy (independent of AI model)

```python
class MedicalExpertiseManifold(IMAOEngine):
    """Verify medical accuracy.
    
    Works with OpenAI, Claude, Gemini, local models,
    or any commercial AI system.
    """
    
    def material_causality(self, response: str, rag_context: str) -> dict:
        # Check against medical knowledge base
        medical_facts = extract_medical_claims(response)
        verified_facts = verify_against_database(medical_facts)
        
        score = len(verified_facts) / max(len(medical_facts), 1)
        return {"passed": score > 0.8, "score": score, "metadata": {}}
```

### Type 3: Bias Detection Manifold (Universal)

**Use Case:** HR, lending, hiring decisions (works with any AI vendor)
**Focus:** Detect and prevent biased recommendations (model-agnostic)

```python
class BiasDetectionManifold(IMAOEngine):
    """Detect bias in AI responses.
    
    Works regardless of whether the AI is from:
    - OpenAI / Azure OpenAI
    - Anthropic Claude
    - Google Gemini
    - Amazon Bedrock
    - Or any other vendor
    """
    
    def __init__(self):
        self.protected_attributes = ["race", "gender", "age", "religion"]
    
    def probability_entropy(self, response: str) -> dict:
        # Check for demographic stereotyping
        bias_score = calculate_bias_score(response, self.protected_attributes)
        
        return {
            "passed": bias_score < 0.3,  # Low bias
            "score": 1.0 - bias_score,
            "metadata": {"bias_score": bias_score}
        }
```

### Type 4: Security & Privacy Manifold (Universal)

**Use Case:** All enterprises (works with any AI vendor)
**Focus:** Prevent data leakage and security violations (model-independent)

```python
class SecurityManifold(IMAOEngine):
    """Detect security and privacy violations.
    
    Works with any commercial AI platform:
    OpenAI, Azure, Claude, Gemini, Bedrock, etc.
    Your security rules apply consistently across all models.
    """
    
    def axiomatic_invariance(self, axioms: list, response: str) -> dict:
        # Check for credential leakage, PII exposure, etc.
        security_violations = []
        
        if contains_credentials(response):
            security_violations.append("Credentials leaked")
        if contains_pii(response):
            security_violations.append("PII exposed")
        if contains_secrets(response):
            security_violations.append("Secrets exposed")
        
        return {
            "passed": len(security_violations) == 0,
            "score": 1.0 if len(security_violations) == 0 else 0.0,
            "metadata": {"violations": security_violations}
        }
```

---

## Integration with IIAE (Universal Pattern)

### Step 1: Implement Your Manifold

**Works identically whether using OpenAI, Azure, Claude, Gemini, or any AI vendor:**

```python
from iiae.mao import IMAOEngine

class YourManifold(IMAOEngine):
    """Your custom verification layer.
    
    This manifold will work with ANY commercial AI model.
    Switch vendors without changing this code.
    """
    def material_causality(self, response: str, rag_context: str) -> dict:
        # Your implementation (AI-model-agnostic)
        pass
    
    def axiomatic_invariance(self, axioms: list, response: str) -> dict:
        # Your implementation (AI-model-agnostic)
        pass
    
    # ... other filters ...
```

### Step 2: Register Your Manifold

**Use the same registration code regardless of AI vendor:**

```python
from iiae.mao.registry import register_engine

register_engine("your_manifold", YourManifold)
```

### Step 3: Use in IIAE Configuration

**Works with any AI model provider:**

```python
from iiae import validate, IIAEConfig

# These all work identically with your manifold:

# With OpenAI:
response = openai_client.generate(...)
result = validate(query, response, context, config=IIAEConfig(mao_engine_name="your_manifold"))

# With Azure OpenAI:
response = azure_client.generate(...)
result = validate(query, response, context, config=IIAEConfig(mao_engine_name="your_manifold"))

# With Anthropic Claude:
response = claude_client.generate(...)
result = validate(query, response, context, config=IIAEConfig(mao_engine_name="your_manifold"))

# With Google Gemini:
response = gemini_client.generate(...)
result = validate(query, response, context, config=IIAEConfig(mao_engine_name="your_manifold"))

# Your verification logic is the same for all!
```

### Step 4: Inspect Results

```python
if result["verified"]:
    print("✓ Approved")
    for filter_name, filter_result in result["mao"].items():
        print(f"  {filter_name}: {filter_result['score']:.2f}")
else:
    print("✗ Blocked")
    print(f"Reason: {result['error']}")
```

---

## Examples

### Example 1: Financial Services Manifold

```python
from iiae.mao import IMAOEngine

class FinancialManifold(IMAOEngine):
    """Manifold for banking and financial services."""
    
    def __init__(self):
        self.max_credit_limit = 1_000_000
        self.max_transaction = 100_000
    
    def axiomatic_invariance(self, axioms: list, response: str) -> dict:
        # Extract numbers from response
        amounts = extract_monetary_amounts(response)
        
        violations = []
        for amount in amounts:
            if amount > self.max_credit_limit:
                violations.append(f"Amount {amount} exceeds credit limit")
            if amount > self.max_transaction:
                violations.append(f"Amount {amount} exceeds transaction limit")
        
        return {
            "passed": len(violations) == 0,
            "score": 1.0 if len(violations) == 0 else 0.0,
            "metadata": {"violations": violations}
        }
```

### Example 2: Healthcare Manifold

```python
class HealthcareManifold(IMAOEngine):
    """Manifold for healthcare AI."""
    
    def __init__(self):
        self.fda_approved_drugs = load_fda_database()
    
    def material_causality(self, response: str, rag_context: str) -> dict:
        # Extract drug recommendations
        drugs = extract_drug_names(response)
        
        approved = sum(1 for drug in drugs if drug in self.fda_approved_drugs)
        
        if not drugs:
            score = 1.0
        else:
            score = approved / len(drugs)
        
        return {
            "passed": score > 0.9,  # 90% must be FDA-approved
            "score": score,
            "metadata": {
                "approved_count": approved,
                "total_count": len(drugs)
            }
        }
```

---

## Compliance Considerations

### Auditability

Every manifold decision must be traceable:

```python
return {
    "passed": True,
    "score": 0.95,
    "metadata": {
        "origin_engine": "your_manifold",
        "check_type": "material_causality",
        "timestamp": datetime.now().isoformat(),
        "evidence": [  # ← Audit trail
            {"fact": "claim_1", "source": "context_1"},
            {"fact": "claim_2", "source": "context_2"}
        ]
    }
}
```

### Reproducibility

Same inputs → Same outputs (deterministic):

```python
# Good: Deterministic
def score_response(response: str, context: str) -> float:
    return len(response) / len(context)

# Bad: Non-deterministic
def score_response(response: str, context: str) -> float:
    return random.random()  # ✗ Different each time!
```

### Fairness

Your manifold should not discriminate:

```python
# ✗ Bad: Discriminates by demographic
def probability_entropy(self, response: str) -> dict:
    if "female" in response:
        return {"score": 0.5}  # Lower score for women
    return {"score": 0.9}

# ✓ Good: Same scoring for everyone
def probability_entropy(self, response: str) -> dict:
    entropy = calculate_confidence_entropy(response)
    return {"score": entropy}
```

### Explainability

Your scores should be explainable:

```python
return {
    "passed": score > 0.7,
    "score": score,
    "metadata": {
        "explanation": (
            f"Response grounded in {grounded_facts} of {total_facts} facts. "
            f"Hallucination risk: {1.0 - score:.1%}"
        ),
        "evidence": {...}
    }
}
```

---

## Checklist for Implementation (Universal Pattern)

- [ ] Implement all four filters (works with any AI model)
- [ ] Return correct data structure (model-independent)
- [ ] Ensure deterministic scoring (AI vendor-agnostic)
- [ ] Add comprehensive metadata for auditability
- [ ] Handle exceptions gracefully (universal error handling)
- [ ] Register manifold (same registration for all vendors)
- [ ] Test with IIAE (same test suite for all)
- [ ] Verify CTM receipts (portable across vendors)
- [ ] Document domain-specific rules
- [ ] Test compliance scenarios (works with any AI)
- [ ] Performance test (latency per filter)
- [ ] Deploy to production (same deployment for all vendors)

---

## Next Steps (Works with Any AI Vendor)

1. **Review** enterprise integration guide: [ENTERPRISE_RAG_INTEGRATION.md](./ENTERPRISE_RAG_INTEGRATION.md)
2. **Study** example implementation: [enterprise_integration_complete.py](../examples/enterprise_integration_complete.py)
3. **Test** your manifold: `pytest tests/test_enterprise_integration.py`
4. **Deploy** to production (same pattern for OpenAI, Azure, Claude, Gemini, or any vendor)

---

## Questions?

- Architecture details: See [ARCHITECTURE.md](./ARCHITECTURE.md)
- API reference: See [API_REFERENCE.md](./API_REFERENCE.md)
- Quick start: See [QUICK_START.md](../QUICK_START.md)
