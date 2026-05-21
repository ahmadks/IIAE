# IIAE/IDICOC-DSE Framework: SDK vs Reference Core

> **Intelligent Invariant Audit Engine (IIAE) & Invariant Data Integrity Chain-of-Custody (IDICOC)**
> *The deterministic, cryptographically verifiable safety and compliance layer for Enterprise Generative AI.*

---

## 🌟 Architectural Separation

The IIAE repository is divided into two distinct, decoupled packages designed to meet the rigorous demands of enterprise compliance and high-performance engineering:

```
                            [ Generative Model (LLM) Output ]
                                            │
                                            ▼
                  ┌───────────────────────────────────────────────────┐
                  │            IIAE PRODUCT ENVIRONMENT               │
                  └───────────────────────────────────────────────────┘
                                            │
                   ┌────────────────────────┴────────────────────────┐
                   ▼                                                 ▼
     ┌───────────────────────────┐                     ┌───────────────────────────┐
     │   IIAE SDK (Production)   │                     │   IIAE Demo (Reference)   │
     │      Directory: iiae/     │                     │   Directory: iiae_demo/   │
     ├───────────────────────────┤                     ├───────────────────────────┤
     │ • 100% Deterministic      │                     │ • Advanced Neural Engine  │
     │ • Zero ML Dependencies    │                     │ • Sentence Transformers   │
     │ • High-performance Gating │                     │ • DeBERTa-v3 NLI Model    │
     │ • Negation-aware DQE-Min  │                     │ • Internal MiniRAG Layer  │
     │ • CTM Forensic Receipts   │                     │ • 7-stage IDICOC Pipeline │
     │ • Ontological MAO Level 1 │                     │ • Research & Blueprint    │
     └───────────────────────────┘                     └───────────────────────────┘
```

> [!IMPORTANT]
> **The Demo Core (`iiae_demo/`) is a Reference Implementation (Blueprint)**. It serves to demonstrate how a deep neural evaluation pipeline (using embeddings, logical entailment, and information retrieval) integrates with the deterministic standards.
>
> **The SDK (`iiae/`) is the Production Standard**. In real-world enterprise deployments (such as Banks, SaaS platforms, and regulated LLMOps), vendors and integrators **must use the SDK** and adapt or plug in their own proprietary models, weights, and pipelines.

---

## 📦 Package Matrix

| Feature / Metric | IIAE SDK (`iiae/`) | IIAE Demo Core (`iiae_demo/`) |
| :--- | :--- | :--- |
| **Primary Focus** | Production-grade runtime gating | Research sandbox & deep semantic reference |
| **Dependencies** | Standard Python Library (Pure & ultra-fast) | `PyTorch`, `Transformers`, `SentenceTransformers` |
| **Model Requirements** | **None** (Zero ML model overhead) | MiniLM embedder, DeBERTa contradiction model |
| **Performance** | Sub-millisecond latency ($<1\text{ms}$) | Medium-high latency (GPU/CPU inference model) |
| **Determinism** | **100% Deterministic** | Stochastic/approximate semantic scoring |
| **Forensic Trust** | CTM Receipts & SHA-256 state tracking | 7-stage Merkle DAG Ledger / Blockchain verification |
| **Execution Path** | Local context negation-aware heuristic | Semantic vector space cosine similarity & NLI |

---

## 🛠️ Installation

### 1. Production SDK (Lightweight & Deterministic)
Perfect for microservices, edge devices, Serverless platforms, and highly regulated offline banking systems:
```bash
pip install -e .
```

### 2. Full Architecture (SDK + Reference Core)
Required for testing the reference pipeline, research, and exploring advanced semantic evaluations:
```bash
pip install -e ".[core]"
```

---

## 🚀 Quick Starts

### 1. The Production SDK (Universal Gating)
The core production runtime. It uses the `IIAESupervisor` to analyze AI completions against constraints locally with zero overhead and full determinism:

```python
from iiae import IIAESupervisor, IIAEConfig, IntegrityError

# 1. Initialize with strict enterprise boundaries
config = IIAEConfig(
    ds_threshold=0.3,          # Maximum tolerable deviation score
    strict_mode=True,          # Active circuit breaker for repeated drift
    timeout_ms=300,            # Maximum allowed evaluation latency
    enable_mao_filters=True    # Run MAO Ontological filters (Axioms, Causality)
)
supervisor = IIAESupervisor(config)

# 2. Define transaction context
prompt = "Determine account status for Client 901."
rag_context = "Accredited accounts must maintain a balance of over $100,000."
ai_response = "Client 901 is accredited. Balance is currently at $15,000."  # Violates A1!

# 3. Verify compliance
try:
    state = supervisor.verify(prompt, ai_response, rag_context)
    print(f"✅ Compliance Verified! CTM Seal: {state.receipt['ctm_seal']}")
except IntegrityError as e:
    print(f"⚠️ INTEGRITY VIOLATION BLOCKED: {e}")
```

### 2. The Reference Core (7-Stage Neural Pipeline Showcase)
Demonstrates the full mathematical specification defined in `IIAE_IDICOC-DSE.pdf` using deep NLI contradiction and embeddings:

```python
from iiae_demo.pipeline import IIAE_Pipeline

# Initialize the 7-stage neural verification engine (with lazy-loading)
pipeline = IIAE_Pipeline(epsilon=0.4)

prompt = "Generate credit report summary."
context = "Credit applications must be encrypted. Key rotation must be enabled."
response = "No encryption protocol exists. Key rotation is forbidden."

# Run the 7-stage verification loop
receipt = pipeline.execute(prompt, context, response)

print(f"System State: {receipt['status']}")
print(f"Deviation Score (Ds): {receipt['ds']}")
print(f"S1 Transition Proof: {receipt['stages']['S1_proof']}")
```

---

## 🧩 Implementing Custom Advanced Modules (Guidelines for Integrators)

When moving beyond the DQE-Minimal heuristical engine in production, companies **should not import `iiae_demo` directly**. Instead, they should adapt the SDK classes (`InvariantEngine`, `IntegrityEvaluator`) or extend the `IIAESupervisor` using their proprietary corporate stacks:

### Custom Neural Evaluator Adapter Example
```python
from iiae.integrity import IntegrityEvaluator
from iiae.dqe import classify_ds

class ProprietaryNeuralEvaluator(IntegrityEvaluator):
    def __init__(self, my_embedding_model, threshold=0.4):
        super().__init__(threshold=threshold)
        self.model = my_embedding_model

    def evaluate(self, response: str, axioms: list):
        # 1. Generate embeddings using your internal, secure company API
        resp_emb = self.model.embed(response)
        ax_embs = [self.model.embed(ax) for ax in axioms]
        
        # 2. Run custom domain-specific semantic alignment
        sims = [cosine_similarity(resp_emb, ae) for ae in ax_embs]
        mean_sim = sum(sims) / len(sims)
        
        # 3. Calculate deviation and map to standard epistemic states
        ds = 1.0 - mean_sim
        return ds, classify_ds(ds)
```

---

## 📋 Documentation

### 🚀 Getting Started (Read in This Order)

1. **[docs/integration/ENTERPRISE_INTEGRATION_GUIDE.md](./docs/integration/ENTERPRISE_INTEGRATION_GUIDE.md)** — **START HERE FOR PRODUCTION**
   - Complete step-by-step guide for junior developers
   - Banking example with full architectural walkthrough
   - Production deployment checklist
   - Troubleshooting guide with solutions

2. **[examples/banking/README.md](./examples/banking/README.md)** — **PRACTICAL WORKING EXAMPLE**
   - Complete, runnable banking assistant code
   - Three real scenarios (pass/fail/violation)
   - How to adapt to your bank
   - Audit trail interpretation guide

### 📚 Core Documentation

* 📊 **[docs/analysis/COHERENCE_ANALYSIS.md](./docs/analysis/COHERENCE_ANALYSIS.md)** — Code vs. IDICOC-DSE handbook comparison (for architects/reviewers)

* 🏗️ **[docs/architecture/ARCHITECTURE.md](./docs/architecture/ARCHITECTURE.md)** — System design overview:
  - Four-layer Invariant Stack (MAII-ISG, DQE, CTM, IDICOC Pipeline)
  - Safe Harbor tier definitions
  - Common integration patterns

* 🧮 **[docs/architecture/MATHEMATICS.md](./docs/architecture/MATHEMATICS.md)** — Mathematical foundation:
  - Formal $D_s$ definition
  - Roadmap to formal compliance

* 📚 **[docs/API_REFERENCE.md](./docs/API_REFERENCE.md)** — Complete SDK API reference with examples

* 🔐 **[examples/mao/COPILOT_INTEGRATION.md](./examples/mao/COPILOT_INTEGRATION.md)** — Enterprise Copilot integration (OEM-ready semantic engines)

### ⚙️ Configuration & Operations

* 📝 **[docs/auditing/audit_logging.md](./docs/auditing/audit_logging.md)** — Audit log configuration and SIEM integration

* 🔍 **[docs/auditing/self_auditing_mao_engines.md](./docs/auditing/self_auditing_mao_engines.md)** — Custom semantic filters

### ⚖️ Compliance & Security

* **[COMPLIANCE.md](./COMPLIANCE.md)** — EU AI Act alignment
* **[SECURITY.md](./SECURITY.md)** — Security hardening guides

---

## 🧪 Testing and Verification

Run the entire compliance validation test suite (containing 40 high-fidelity and compliance scenario tests) with `pytest`:
```bash
pytest run_all_tests.py
```
