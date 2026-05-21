# Enterprise Integration: IIAE Between AI and RAG

**Target Audience:** Enterprise architects, OEM partners, AI integrators  
**Use Case:** Any Commercial AI Platform (Microsoft Copilot, Azure OpenAI, OpenAI ChatGPT, Anthropic Claude, Google Gemini, Amazon Bedrock, Cohere, Mistral)  
**Complexity:** Intermediate  
**Time to Implement:** 1-2 weeks

---

## 1. Purpose

The Invariant Integrity Architecture Engine (IIAE) provides a model‑agnostic, deterministic verification layer that evaluates AI outputs against retrieved context and produces a cryptographic CTM receipt for audit, compliance, and reproducibility.

It integrates seamlessly with any AI model and any RAG system, without modifying the model.

---

## 2. Universal Integration Pattern

This pattern is identical for all commercial AI systems (Copilot, Azure OpenAI, OpenAI, Claude, Gemini, Bedrock, Cohere, Mistral):

```
User Query
    ↓
RAG Retrieval (documents, policies, rules)
    ↓
AI Model (LLM)
    ↓
IIAE Verification Layer
    ↓
Approved Response + CTM Receipt
```

The IIAE sits after the model and before the user, acting as a deterministic gatekeeper.

---

## 3. Required Inputs

The enterprise system must provide:

- `prompt` → the user query
- `response` → the model output
- `context` → RAG documents, policies, or rules

The IIAE does not require access to the model internals.

---

## 4. Verification Contract

Every integration follows the same 5‑step contract:

1. Retrieve context
2. Generate model response
3. Call `IIAE.validate(prompt, response, context)`
4. Receive deterministic classification + CTM receipt
5. Approve or block the response

This contract is stable across all vendors and all models.

---

## 5. CTM Receipt

The CTM is a cryptographic fingerprint containing:

- Merkle root of extracted axioms
- Prompt hash
- Response hash
- Deviation score
- Timestamp
- Model identifier
- CTM version

It is **not** a log.
It is portable, verifiable evidence for compliance and audit.

---

## 6. Logging & Audit

Audit logs are enterprise‑controlled.
The IIAE emits structured JSON audit records that can be redirected to:

- Azure Monitor
- Splunk
- Elastic
- Datadog
- SIEM systems
- Local files

The CTM remains deterministic and independent of logging configuration.

---

## 7. Optional OEM Semantic Layer (MAO)

Enterprises may optionally plug in their own semantic engine to define their manifold:

- Embeddings
- Entailment models
- Safety classifiers
- Grounding rules
- Domain‑specific thresholds

This is optional and does not affect the core IIAE contract.

---

## 8. Minimal Integration Code (Universal)

```python
from iiae import validate, IIAEConfig

# Assuming `rag` and `llm` are initialized elsewhere
# Example: rag = YourRAGSystem(), llm = YourLLMClient()

user_query = "What is the capital of France?"

# 1. RAG retrieves context
context = rag.retrieve(user_query) # Ensure context is a string or has a 'text' attribute

# 2. AI model generates a response
response = llm.generate(prompt=user_query, context=context) # Ensure context is passed correctly to LLM

# 3. IIAE verifies the response
result = validate(
    prompt=user_query,
    response=response,
    context=context, # Ensure this is the same context used by the LLM
    config=IIAEConfig(
        ds_threshold=0.4, # Adjust based on your risk tolerance
        enable_mao_filters=True, # Optional: Set to False to disable MAO filters
        # mao_engine_name="your_custom_semantic_engine" # Optional: If you have a custom MAO engine
    )
)

# 4. CTM receipt is generated automatically as part of 'result'
#    receipt = result["receipt"]

# 5. Enterprise decides what to do
if result["verified"]:
    # Response is approved by IIAE
    print(f"✅ Approved Response: {response}")
    print(f"CTM Receipt: {result['receipt']}")
    # return response, result["receipt"]
else:
    # Response is blocked by policy or integrity violation
    print(f"❌ Blocked by policy. Reason: {result.get('error', 'Unknown reason')}")
    print(f"CTM Receipt (for audit): {result.get('receipt', 'N/A')}")
    # return "Blocked by policy", result.get("receipt")

```
This works with any model and any RAG system.

**Important — Do Not Assume Correctness Without Verification:**

- **Verify returned structure:** Programmatically check `result` contains the keys `verified`, `ds`, and `receipt` before using them.
- **Validate CTM receipts:** Use `iiae.audit(receipt)` (or `iiae.audit(state)`) to cryptographically verify the CTM before trusting it for audit or compliance workflows.
- **Ensure context parity:** Confirm the `context` passed to your LLM is the *same* `context` value you pass to `validate()`; mismatched context is a common source of false positives/negatives in deviation scores.
- **Handle missing fields defensively:** Don't assume `receipt` or `ds` always exist; implement graceful fallback paths and logging for blocked responses.

Run the minimal verification test included in this repository to check your environment and integration before declaring success. Example command:

```bash
pytest tests/test_minimal_integration.py -q
```

The test executes a minimal end‑to‑end flow using simple prompt/context/response inputs, verifies the `validate()` contract, and attempts to audit the generated CTM if present.

---

## 9. Deployment Requirements

- Deterministic environment for CTM hashing
- Logging destination configured by enterprise
- Optional OEM semantic engine registered (if used)
- Thresholds tuned per domain
- No changes to the AI model or RAG system are required.

---

## 10. Summary

The IIAE provides a universal, deterministic, model‑agnostic verification layer that fits into any enterprise AI pipeline.
It evaluates AI outputs, enforces policy boundaries, and produces cryptographic CTM receipts for audit and compliance.
The integration pattern is identical across all commercial AI systems.

**Solution:**
```python
# Current config
config = IIAEConfig(ds_threshold=0.1)  # Too strict!

# Adjust
config = IIAEConfig(ds_threshold=0.4)  # More reasonable
```

### Issue: "Deviation scores don't match policy violations"

**Cause:** RAG context doesn't contain the relevant policies.

**Solution:**
```python
# Ensure RAG retrieves policy documents
context = rag.retrieve(
    user_query,
    filters={"document_type": "policy"}  # ← Add filters
)

# Verify context quality
print(f"Context documents: {context['documents']}")
print(f"Context length: {len(context['text'])}")
```

### Issue: "CTM receipt is invalid or missing"

**Cause:** Circuit breaker may have tripped.

**Solution:**
```python
from iiae import IIAESupervisor

supervisor = IIAESupervisor()
state = supervisor.verify(query, response, context)

# Check circuit breaker status
print(f"Circuit state: {supervisor.circuit_breaker.state}")
# Possible states: CLOSED (normal), OPEN (tripped), HALF_OPEN (recovering)
```

### Issue: "Optional MAO filters not running"

**Cause:** Dependencies not installed.

**Solution:**
```bash
# Install semantic dependencies
pip install torch sentence-transformers

# Verify
python -c "import torch; print('✓ torch installed')"
```

---

## Next Steps (Universal for All AI Vendors)

1. **Review:** [Semantic Manifold Specification](./OEM_MANIFOLD_SPECIFICATION.md) — Works with any AI model
2. **Implement:** [Full Enterprise Example](../examples/enterprise_integration_complete.py) — Replace mock LLM with your provider
3. **Test:** `pytest tests/test_enterprise_integration.py` — Same tests for all vendors
4. **Deploy:** Follow deployment checklist above — Same pattern for OpenAI, Azure, Claude, Gemini, etc.

---

## Questions?

- **Quick Start:** See [QUICK_START.md](../QUICK_START.md)
- **API Reference:** See [API_REFERENCE.md](./API_REFERENCE.md)
- **Architecture Deep Dive:** See [ARCHITECTURE.md](./ARCHITECTURE.md)
