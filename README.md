# IIAE — Intelligent Invariant Audit Engine

**IIAE** is an enterprise-grade framework for deterministic audit, compliance and forensic verification of generative AI outputs.

It combines:
- a production-grade SDK with **zero ML model dependencies**
- a reference/demo core for advanced semantic evaluation
- cryptographically verifiable receipts
- formal deviation scoring and drift detection
- compliance and audit logging guidance

---

## What this repository contains

### `iiae/` — Production SDK
A lightweight, deterministic audit engine designed for regulated enterprise deployments.

Key capabilities:
- `IIAESupervisor` for runtime verification of LLM outputs
- `IIAEConfig` for thresholding, timeout, circuit breaker and logging
- deterministic `DQE` scoring and epistemic state classification
- `CTM` forensic receipts and receipt verification
- `MAO` auditing, engine registration, and modular extension points
- zero ML dependencies in production

### `iiae_demo/` — Reference implementation
A research-grade reference pipeline implementing the full IIAE / IDICOC-DSE architecture.

Key capabilities:
- 7-stage verification pipeline with lazy-loaded modules
- Axiom Entropy Module (AEM)
- Invariant State Generator (ISG)
- Dynamic Schema Extraction (DSE)
- Creative Manifold Constructor (CMC)
- Deviation Quantification Engine (DQEReal)
- Custodial Traceability Module (CTM)
- semantic evaluation with embeddings + NLI

### `examples/`
Practical integration examples:
- `examples/banking/` — banking assistant example
- `examples/mao/` — Copilot / OEM integration examples
- `examples/bank_rag/` — RAG pipeline example
- `examples/onboarding/` — onboarding pipeline sample

### `docs/`
Comprehensive documentation and architecture guidance:
- `docs/introduction/INTRODUCTION.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/MATHEMATICS.md`
- `docs/architecture/SDK_ARCHITECTURE.md`
- `docs/API_REFERENCE.md`
- `docs/auditing/COMPLIANCE.md`
- `docs/auditing/audit_logging.md`
- `docs/auditing/self_auditing_mao_engines.md`
- `docs/integration/ENTERPRISE_INTEGRATION_GUIDE.md`
- `docs/integration/OEM_MANIFOLD_SPECIFICATION.md`
- `docs/integration/ENTERPRISE_RAG_INTEGRATION.md`
- `docs/integration/UNIVERSAL_AI_PATTERN.md`

### Top-level supporting files
- `SECURITY.md`
- `LICENSE`
- `LICENSE.md`
- `NOTICE`
- `pyproject.toml`
- `requirements.txt`
- `run_all_tests.py`
- `streamlit_app.py`

---

## Technologies

### Core
- Python `>=3.8`
- `setuptools`

### Production dependencies
- `numpy`
- `pandas`
- `python-dotenv`

### Optional reference/demo dependencies
- `sentence-transformers`
- `transformers`
- `torch`
- `networkx`
- `scikit-learn`
- `sentencepiece`

### UI / examples
- `streamlit`
- `PyPDF2`

### Testing
- `pytest`

---

## Key features

- **Deterministic compliance verification**
- **Zero ML overhead in the SDK**
- **Cryptographic CTM receipts**
- **Deviation score (`D_s`) and epistemic state tracking**
- **Circuit breaker for repeated drift**
- **Pluggable MAO audit engines**
- **Structured audit record generation**
- **Enterprise integration patterns**
- **Formal architecture and mathematical foundation**
- **EU AI Act / audit logging alignment**

---

## Installation

### Minimal production SDK
```bash
pip install -e .
```

### Full architecture + demo core
```bash
pip install -e ".[core]"
```

> Optionally create a `.env` file with `HF_TOKEN` if you need Hugging Face model downloads for demo or example pipelines.

---

## Quick start

### Production SDK
```python
from iiae import IIAESupervisor, IIAEConfig, IntegrityError

config = IIAEConfig(
    ds_threshold=0.3,
    strict_mode=True,
    timeout_ms=300,
    enable_mao_filters=True
)
supervisor = IIAESupervisor(config)

prompt = "Determine account status for Client 901."
rag_context = "Accredited accounts must maintain a balance of over $100,000."
ai_response = "Client 901 is accredited. Balance is currently at $15,000."

try:
    state = supervisor.verify(prompt, ai_response, rag_context)
    print(f"✔️ Verified: {state.receipt['ctm_seal']}")
except IntegrityError as e:
    print(f"⚠️ Integrity violation blocked: {e}")
```

### Reference pipeline
```python
from iiae_demo.pipeline import IIAE_Pipeline

pipeline = IIAE_Pipeline(epsilon=0.4)

prompt = "Generate credit report summary."
context = "Credit applications must be encrypted. Key rotation must be enabled."
response = "No encryption protocol exists. Key rotation is forbidden."

receipt = pipeline.execute(prompt, context, response)

print(receipt["status"])
print(receipt["ds"])
print(receipt["stages"]["S1_proof"])
```

---

## Project structure

- `iiae/` — production SDK package
- `iiae_demo/` — reference demo package
- `docs/` — architecture, API reference, integration guides
- `examples/` — runnable integration examples
- `tests/` — automated test suite
- `requirements.txt` — dependency list
- `pyproject.toml` — packaging metadata
- `run_all_tests.py` — test runner
- `streamlit_app.py` — demo UI launcher

---

## Documentation and learning path

Start here:
1. `docs/introduction/INTRODUCTION.md`
2. `docs/integration/ENTERPRISE_INTEGRATION_GUIDE.md`
3. `docs/API_REFERENCE.md`
4. `docs/architecture/ARCHITECTURE.md`
5. `docs/architecture/MATHEMATICS.md`

Additional references:
- `docs/auditing/audit_logging.md`
- `docs/auditing/self_auditing_mao_engines.md`
- `docs/integration/OEM_MANIFOLD_SPECIFICATION.md`

---

## Testing

Run the test suite with:
```bash
pytest run_all_tests.py
```

---

## License

See `LICENSE` and `LICENSE.md` for terms and notices.

---

## Notes

- `iiae` is the production-ready deterministic enforcement layer.
- `iiae_demo` is a reference implementation for research, semantic verification, and demo purposes.
- The repository is intended for enterprise use cases where auditability, traceability, and compliance are required.
