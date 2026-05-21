# Enterprise Architecture Diagrams

**Visual Reference for Enterprise Integration**

---

## Diagram 1: IIAE in Enterprise Pipeline (RAG + LLM + Verification)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ENTERPRISE SYSTEM                           │
│                                                                     │
│  ┌─────────────┐                                                   │
│  │  User Query │                                                   │
│  └──────┬──────┘                                                   │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────────────┐                                           │
│  │   RAG System        │  ← Retrieves context from policies,       │
│  │  • Document Store   │    documents, knowledge base              │
│  │  • Vector DB        │                                           │
│  │  • Semantic Search  │                                           │
│  └──────┬──────────────┘                                           │
│         │                                                           │
│         │  Relevant Documents & Context                            │
│         ▼                                                           │
│  ┌─────────────────────┐                                           │
│  │    AI Model         │  ← LLM (OpenAI, Azure OpenAI,             │
│  │  • LLM              │    Copilot, Local, etc.)                  │
│  │  • Generation       │    Generates response using context       │
│  │  • Reasoning        │                                           │
│  └──────┬──────────────┘                                           │
│         │                                                           │
│         │  Generated Response                                      │
│         ▼                                                           │
│  ┌────────────────────────────────────────┐                        │
│  │     IIAE VERIFICATION LAYER            │  ← Safety Gate         │
│  │  ┌──────────────────────────────────┐  │                        │
│  │  │ 1. Extract Axioms from Context   │  │                        │
│  │  └──────────────────────────────────┘  │                        │
│  │  ┌──────────────────────────────────┐  │                        │
│  │  │ 2. Compute Deviation Score (Ds)  │  │  Deviation Scoring     │
│  │  │    Against Business Rules        │  │                        │
│  │  └──────────────────────────────────┘  │                        │
│  │  ┌──────────────────────────────────┐  │                        │
│  │  │ 3. Run Optional Semantic Filters │  │  MAO (Optional)        │
│  │  │    • Material Causality          │  │                        │
│  │  │    • Axiomatic Invariance        │  │                        │
│  │  │    • Geoclimatic Synchrony       │  │                        │
│  │  │    • Probability Entropy         │  │                        │
│  │  └──────────────────────────────────┘  │                        │
│  │  ┌──────────────────────────────────┐  │                        │
│  │  │ 4. Generate CTM Receipt          │  │  Cryptographic Proof   │
│  │  │    (Non-repudiable evidence)     │  │                        │
│  │  └──────────────────────────────────┘  │                        │
│  └────────────┬─────────────────────────────┘                      │
│               │                                                     │
│               ├─ IF Verified:                                      │
│               │  └─ Return (Response + CTM Receipt)                │
│               │                                                     │
│               └─ IF Blocked:                                       │
│                  └─ Block + Log Violation + Generate Receipt       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Diagram 2: IIAE Core Verification Flow

```
                          ┌─────────────────┐
                          │  User Query     │
                          │  AI Response    │
                          │  RAG Context    │
                          └────────┬────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
           ┌─────────────────────┐      ┌──────────────────┐
           │  Extract Axioms     │      │  DQE Scoring     │
           │  from Context       │      │  (Deviation)     │
           │                     │      │                  │
           │ Rules like:         │      │ Ds = deviation   │
           │ - "Max limit:       │      │      coefficient │
           │    $1M"             │      │                  │
           │ - "Always         │      │ 0.0 = Perfect    │
           │    encrypt"         │      │ 1.0 = Violation  │
           └────────┬────────────┘      └────────┬─────────┘
                    │                            │
                    │         Compare            │
                    └──────────┬─────────────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Deviation Detected? │
                    └──────────┬───────────┘
                               │
                ┌──────────────┼──────────────┐
                │              │              │
           Low (OK)         Medium         High (Violation)
             ▼                ▼               ▼
         Ds < 0.4         0.4 < Ds < 0.7   Ds > 0.7
             │              │               │
             │              │        ┌──────▼─────────┐
             │              │        │ MAO (Optional) │
             │              │        │ 4 Filters      │
             │              │        └──────┬─────────┘
             │              │               │
             │              │         ┌─────▼──────────┐
             │              │         │ Re-evaluate    │
             │              │         │ with semantics │
             │              │         └─────┬──────────┘
             │              │               │
             │              │         ┌─────▼──────────┐
             │              │         │ Final decision │
             │              │         └─────┬──────────┘
             │              │               │
      ┌──────▼──────┬───────┴───────┬──────▼──────┐
      │             │               │             │
   APPROVED     WARNING/REVIEW    BLOCKED      ESCALATE
      │             │               │             │
      └─────────────┼───────────────┼─────────────┘
                    │               │
                    └───────┬───────┘
                            │
                    ┌───────▼──────────┐
                    │  CTM Receipt     │
                    │  Generated       │
                    │  (All cases)     │
                    └───────┬──────────┘
                            │
                ┌───────────┴──────────────┐
                │                          │
           ✓ Send to User      ✗ Log Violation
                │                          │
           Response +              Event + Receipt
           Receipt                        │
                                   Escalate to
                                   Compliance
```

---

## Diagram 3: CTM Receipt Structure & Integrity

```
┌─────────────────────────────────────────────────────────────┐
│               CTM RECEIPT (Cryptographic)                   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ PAYLOAD (What was verified)                         │   │
│  │                                                     │   │
│  │  • query: "What's our credit limit?"               │   │
│  │  • response: "Up to $500,000 for low risk..."      │   │
│  │  • context_hash: <SHA256 of RAG context>          │   │
│  │  • deviation_score: 0.15                           │   │
│  │  • verified: true                                  │   │
│  │  • timestamp: 2026-05-21T10:30:00Z                │   │
│  │  • mao_results: {                                  │   │
│  │      "material_causality": 0.92,                   │   │
│  │      "axiomatic_invariance": 0.88,                 │   │
│  │      "geoclimatic_synchrony": 0.85,                │   │
│  │      "probability_entropy": 0.91                   │   │
│  │    }                                               │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ SIGNATURE (Proof of integrity)                      │   │
│  │                                                     │   │
│  │  signature: <HMAC-SHA256 over payload>             │   │
│  │  signing_algorithm: HMAC-SHA256                    │   │
│  │  key_id: <IIAE system key>                         │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

AUDIT VERIFICATION:
  verify(receipt) → True/False
  
  ✓ If True:
    - Payload is authentic
    - Not tampered with
    - Can be used as legal evidence
    - Compliance proof
  
  ✗ If False:
    - Payload was modified after signing
    - Do not trust the verification result
    - Potential security incident
```

---

## Diagram 4: OEM Semantic Manifold Integration

```
┌──────────────────────────────────────────────────────────────────┐
│          OEM SEMANTIC MANIFOLD (Pluggable)                       │
│                                                                  │
│  Example: "enterprise_semantic" manifold for banking            │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ FILTER 1: Material Causality                              │ │
│  │ Question: "Is response grounded in facts?"                │ │
│  │ Implementation: Check if claims appear in RAG context     │ │
│  │ Score: 0.92 (92% of claims are grounded)                 │ │
│  │ Passes: ✓ Yes (> 70% threshold)                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ FILTER 2: Axiomatic Invariance                            │ │
│  │ Question: "Does response violate business rules?"         │ │
│  │ Implementation: Check against policies (credit limits,    │ │
│  │                 data retention, compliance rules)          │ │
│  │ Score: 0.88 (No violations detected)                      │ │
│  │ Passes: ✓ Yes                                            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ FILTER 3: Geoclimatic Synchrony                           │ │
│  │ Question: "Is response contextually aligned?"             │ │
│  │ Implementation: Measure semantic similarity with context  │ │
│  │ Score: 0.85 (Response is 85% similar to context)         │ │
│  │ Passes: ✓ Yes (> 50% threshold)                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ FILTER 4: Probability Entropy                             │ │
│  │ Question: "Is confidence appropriately calibrated?"       │ │
│  │ Implementation: Detect over-confident or hedging language │ │
│  │ Score: 0.91 (Confidence is well-calibrated)              │ │
│  │ Passes: ✓ Yes (> 40% threshold)                          │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  FINAL MANIFOLD RESULT:                                         │
│  ✓ All 4 filters pass                                          │
│  → Semantic verification successful                            │
│  → Used by IIAE in final verification decision                │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## Diagram 5: Enterprise Deployment Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                    MICROSOFT ENTERPRISE ARCHITECTURE               │
│                                                                    │
│  ┌──────────────┐                                                 │
│  │ Copilot UI   │                                                 │
│  │ (Web/App)    │                                                 │
│  └──────┬───────┘                                                 │
│         │                                                         │
│  ┌──────▼──────────────────────────────────────────────────────┐ │
│  │  ENTERPRISE APPLICATION SERVER (FastAPI/Node/Django)       │ │
│  │                                                             │ │
│  │  @app.post("/ask")                                         │ │
│  │  def answer_question(query: str):                          │ │
│  │      # Step 1: RAG                                         │ │
│  │      context = rag.retrieve(query)                         │ │
│  │                                                             │ │
│  │      # Step 2: LLM                                         │ │
│  │      response = llm.generate(query, context)               │ │
│  │                                                             │ │
│  │      # Step 3: IIAE Verification                           │ │
│  │      result = validate(                                    │ │
│  │          prompt=query,                                    │ │
│  │          response=response,                               │ │
│  │          context=context,                                 │ │
│  │          config=IIAEConfig(                               │ │
│  │              mao_engine_name="enterprise_semantic"        │ │
│  │          )                                                │ │
│  │      )                                                     │ │
│  │                                                             │ │
│  │      # Step 4: Decision                                   │ │
│  │      if result["verified"]:                               │ │
│  │          return {"response": response, "receipt": ...}    │ │
│  │      else:                                                │ │
│  │          return {"error": "Policy blocked"}               │ │
│  │                                                             │ │
│  └──────┬────────┬──────────────────┬────────────────────────┘ │
│         │        │                  │                          │
│    ┌────▼──┐ ┌───▼────┐ ┌──────────▼──────┐ ┌──────────────┐  │
│    │ RAG   │ │ LLM    │ │   IIAE          │ │ Audit Log    │  │
│    │System │ │Azure   │ │   Verification │ │ (Database)   │  │
│    │       │ │OpenAI  │ │                 │ │              │  │
│    └───────┘ └────────┘ │ Library or API  │ └──────────────┘  │
│                         │                 │                   │
│                         │ • DQE           │ ┌──────────────┐  │
│                         │ • CTM           │ │ Compliance   │  │
│                         │ • MAO Filters   │ │ Dashboard    │  │
│                         │ • Supervisor    │ │              │  │
│                         └─────────────────┘ └──────────────┘  │
│                                                                │
└────────────────────────────────────────────────────────────────┘

GOVERNANCE & COMPLIANCE LAYER:
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│  ✓ All responses verified before reaching user                   │
│  ✓ CTM receipts provide non-repudiable proof                     │
│  ✓ Audit trail for compliance (GDPR, HIPAA, SOX)                │
│  ✓ OEM semantic rules enforced (enterprise policies)             │
│  ✓ Circuit breaker prevents cascading failures                  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

---

## Diagram 6: Decision Tree (Approval vs. Rejection)

```
                     ┌─────────────────────┐
                     │  AI Generated       │
                     │  Response           │
                     └────────┬────────────┘
                              │
                    ┌─────────▼──────────┐
                    │ Compute Ds         │
                    │ (Deviation Score)  │
                    └────────┬────────────┘
                             │
            ┌────────────────┼────────────────┐
            │                │                │
       0.0 - 0.4          0.4 - 0.7        > 0.7
      (Low Risk)      (Medium Risk)    (High Risk)
            │                │                │
            ▼                ▼                ▼
        APPROVED         WARNING/REVIEW     CHECK MAO
            │                │                │
        Return ✓         Flag & Review   Run Optional
        Response             │            Filters
        + CTM              Continue?           │
                             │          ┌──────▼──────┐
                             │          │ All filters │
                             │          │ pass?       │
                             │          └──────┬──────┘
                             │                 │
                             ├─ YES ──────────▶├─ YES → APPROVED
                             │                 │
                             │                 └─ NO → BLOCKED
                             │
                             └─ NO → BLOCKED
                                 (Escalate)
```

---

## How to Use These Diagrams

### For Architecture Review
- Reference Diagram 1 to explain IIAE placement in your enterprise
- Use Diagram 2 to explain verification flow to stakeholders

### For Implementation
- Follow Diagram 5 to design your application server
- Use Diagram 4 to guide OEM semantic manifold development

### For Compliance
- Use Diagram 3 to explain CTM receipts to auditors
- Reference Diagram 6 to document decision logic

### For Training
- Use Diagram 1 as overview slide
- Use Diagrams 2, 3, 4 as technical deep-dives
- Use Diagram 5 for deployment planning

---

## Mermaid Versions (For Automated Diagramming)

These diagrams are also available in Mermaid format for generating live diagrams in documentation:

- See [../integration/ENTERPRISE_RAG_INTEGRATION.md](../integration/ENTERPRISE_RAG_INTEGRATION.md) for Mermaid-based diagrams
