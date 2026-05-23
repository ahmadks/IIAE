# IIAE — Intelligent Invariant Audit Engine

> **IDICOC · IIAE SDK** — A deterministic, coalgebraic audit framework for commercial AI systems.

IIAE wraps any commercial AI (LLM, classifier, RAG pipeline) with a cryptographic notary that **measures dissonance, classifies entropy, and seals every interaction** into a tamper-evident Merkle DAG — without ever blocking or modifying the AI's output.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Modules](#modules)
  - [idicoc\_audit\_flow](#idicoc_audit_flow)
  - [idicoc\_core](#idicoc_core)
  - [idicoc\_utils](#idicoc_utils)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Persistence](#persistence)
- [Audit Modes](#audit-modes)
- [Dissonance Strategies](#dissonance-strategies)
- [Logging](#logging)
- [Testing](#testing)
- [Requirements](#requirements)
- [License](#license)

---

## Overview

IIAE implements the **IDICOC** (Invariant-Deterministic Coalgebraic Custodial) protocol. It provides:

- **Notarial passivity**: the wrapper never rejects, modifies, or delays AI output — it only measures and records.
- **Algebraic correctness**: dissonance `D_s = λ_logic · d_logic` is computed coalgebraically and verified on every interaction.
- **Cryptographic custody**: every audited interaction is appended to a Merkle DAG (`CustodialTraceManager`) producing an unforgeable chain of receipts.
- **Configurable persistence**: AEM entropy events and CTM DAG nodes can be persisted to disk (JSON files), an external database, or kept purely in memory.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Commercial AI / LLM                 │
└────────────────────────┬────────────────────────────┘
                         │ raw input
                         ▼
┌─────────────────────────────────────────────────────┐
│               IDICOCWrapper  (notary)               │
│  ┌──────────────────────────────────────────────┐   │
│  │          IIAEEnterpriseSDKWrapper            │   │
│  │                                              │   │
│  │  1. AEM — Admission & entropy classification │   │
│  │  2. Dissonance Strategy (math | semantic)    │   │
│  │  3. CustodialKernel — coalgebraic pipeline   │   │
│  │     ├─ ISG  (invariant state projection)     │   │
│  │     ├─ DSE  (dynamic schema extraction)      │   │
│  │     ├─ CMC  (manifold constructor)           │   │
│  │     ├─ DQE  (deviation quantifier)           │   │
│  │     └─ CTM  (Merkle DAG custody)             │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  Returns: CanonicalStateDTO + audit receipt         │
└─────────────────────────────────────────────────────┘
```

### Key invariant

Every interaction produces a `CanonicalStateDTO` with:
- `d_s` — total dissonance (`D_s = λ_logic · d_logic`, weights `[0, 1, 0]`)
- `integrity_hash` — SHA-256 of the canonical state
- `audit_receipt` — Merkle node hash sealing the interaction in the DAG

---

## Modules

### `idicoc_audit_flow`

The public SDK layer. This is the only module you need to import.

| File | Purpose |
|---|---|
| [`wrapper_pipeline.py`](idicoc_audit_flow/wrapper_pipeline.py) | `IDICOCWrapper` — the main entry point. Notary adapter implementing `IDICOCWrapperContract`. |
| [`pipeline.py`](idicoc_audit_flow/pipeline.py) | `IIAEEnterpriseSDKWrapper` — orchestrates the full audit pipeline per interaction. |
| [`config.py`](idicoc_audit_flow/config.py) | `AuditConfig` dataclass — all configuration parameters with defaults. |
| [`base.py`](idicoc_audit_flow/base.py) | `CanonicalStateDTO`, `EntropyAnalyzer` (Protocol), `IDICOCWrapperContract` (ABC), `BankEntropyAnalyzer` (example). |
| [`axioms.py`](idicoc_audit_flow/axioms.py) | `AxiomEngine` — injects domain invariants into the PropertyGraph. |
| [`kernel_client.py`](idicoc_audit_flow/kernel_client.py) | `KernelCustodyClient` — seals wrapper commits into the CTM Merkle DAG. |
| [`exceptions.py`](idicoc_audit_flow/exceptions.py) | `WrapperInitializationError` and related SDK exceptions. |

#### `idicoc_audit_flow/strategies/`

| File | Purpose |
|---|---|
| [`mathematical.py`](idicoc_audit_flow/strategies/mathematical.py) | `MathematicalDissonanceStrategy` — 7-component weighted dissonance (token frequency, similarity, hash, embedding distance, etc.). No GPU required. |
| [`semantic.py`](idicoc_audit_flow/strategies/semantic.py) | `SemanticDissonanceStrategy` — NLI-based contradiction detection + cosine embedding distance. Requires `sentence-transformers` and `transformers`. |

#### `idicoc_audit_flow/persistence/`

Pluggable storage backends for optional disk persistence.

| File | Purpose |
|---|---|
| [`backend.py`](idicoc_audit_flow/persistence/backend.py) | Abstract base classes `AEMStorageBackend` and `CTMStorageBackend`. |
| [`file_backend.py`](idicoc_audit_flow/persistence/file_backend.py) | `FileAEMStorage` (JSON) and `FileCTMStorage` (JSON nodes + TXT root hash). |

---

### `idicoc_core`

The deterministic engine. Domain-independent — has no knowledge of the `idicoc_audit_flow` layer.

#### `idicoc_core/runtime/`

| File | Purpose |
|---|---|
| [`config.py`](idicoc_core/runtime/config.py) | `RuntimeConfig` — assembles all core subsystems (Anchor, AEM, ISG, Verifier, CTM, DSE, CMC, DQE) and exposes `kernel_factory()`. |

#### `idicoc_core/core/`

| Subsystem | Module | Purpose |
|---|---|---|
| **AEM** | [`admission/aem.py`](idicoc_core/core/admission/aem.py) | `AnomalousEventManager` — entropy barrier, noise classification (DISCARDED / RECOVERABLE / ADMITTED), EPR metric. Accepts `AEMStorageBackend` for persistence. |
| **CTM** | [`custody/merkle_dag.py`](idicoc_core/core/custody/merkle_dag.py) | `MerkleDAG` + `CustodialTraceManager` — append-only DAG with optional hardware HMAC sealing and `CTMStorageBackend` persistence. |
| **ISG** | [`projection/invariant_state_generator.py`](idicoc_core/core/projection/invariant_state_generator.py) | Generates the canonical invariant state from admitted input. |
| **DSE** | [`dse/dse.py`](idicoc_core/core/dse/dse.py) | `DynamicSchemaExtractor` — updates the PropertyGraph from canonical state. |
| **CMC** | [`manifold/cmc.py`](idicoc_core/core/manifold/cmc.py) | `ManifoldConstructor` — builds the admissible manifold; dynamically updates `epsilon` based on axiom density and dissonance variance. |
| **DQE** | [`deviation/dqe.py`](idicoc_core/core/deviation/dqe.py) | `DeviationQuantifier` — computes `D_s`, projects to manifold when `D_s > epsilon`. |
| **Verifier** | [`verification/verifier.py`](idicoc_core/core/verification/verifier.py) | `InvariantVerifier` — verifies alignment of the canonical state within tolerance. |
| **Graph** | [`graph/property_graph.py`](idicoc_core/core/graph/property_graph.py) | `PropertyGraph` — stores nodes, edges, and active axioms. |
| **Kernel** | [`pipeline/kernel.py`](idicoc_core/core/pipeline/kernel.py) | `CustodialKernel` — 7-stage coalgebraic pipeline (Admission → Projection → Schema → Manifold → Deviation → Verification → CTM Commit). |
| **Anchor** | [`source/anchor.py`](idicoc_core/core/source/anchor.py) | `SourceAnchor` — wraps the constant `k` that anchors the invariant manifold. |

---

### `idicoc_utils`

Shared utilities with no domain dependencies.

| File | Purpose |
|---|---|
| [`logger.py`](idicoc_utils/logger.py) | `get_logger()`, `configure_logging()` — JSON-structured audit logs, configurable destination (stdout, file, Azure, Splunk, Elastic, Datadog, SIEM). |
| [`hashing.py`](idicoc_utils/hashing.py) | `sha256_hex()`, `sha256_dict()`, `hmac_sha256_hex()`, `canonical_json()` — deterministic hashing utilities. |

---

## Quick Start

### Installation

```bash
pip install -r requirements.txt
```

For mathematical mode only (no GPU, no large models):

```bash
pip install numpy scipy pandas python-dotenv pytest
```

For semantic mode:

```bash
pip install sentence-transformers transformers torch scikit-learn
```

### Minimal usage (mathematical mode)

```python
from idicoc_audit_flow.config import AuditConfig
from idicoc_audit_flow.base import BankEntropyAnalyzer
from idicoc_audit_flow.wrapper_pipeline import IDICOCWrapper

config = AuditConfig(
    audit_mode="mathematical",
    rigidity_epsilon=0.35,     # 0.0 = factual, 0.35 = hybrid, 0.7 = creative
    source_name="my_ai_service",
)

analyzer = BankEntropyAnalyzer()   # or implement EntropyAnalyzer Protocol
wrapper  = IDICOCWrapper(config, analyzer)

state = wrapper.process_interaction(
    audit_input="Transfer 500€ from account 1234567890 to 9876543210",
    context_input=["The customer requested a domestic transfer."],
    context_axioms=["All transfers must include a valid account number."],
)

print(state.metadata["d_s"])            # dissonance score
print(state.metadata["correction_flag"])
print(state.integrity_hash)             # SHA-256 of canonical state
```

### With disk persistence

```python
from idicoc_audit_flow.persistence.file_backend import FileAEMStorage, FileCTMStorage

aem_storage = FileAEMStorage("data/aem_entropy.json")
ctm_storage = FileCTMStorage("data/ctm_nodes.json", "data/ctm_root.txt")

wrapper = IDICOCWrapper(
    config, analyzer,
    aem_storage=aem_storage,
    ctm_storage=ctm_storage,
)
```

The DAG and AEM events are automatically reloaded from disk on the next instantiation — continuity is preserved across restarts.

### Direct pipeline execution

```python
result = wrapper.pipeline.execute(
    audit_input="...",
    context_input=["..."],
    context_axioms=["..."],
    epsilon_override=0.5,   # per-call epsilon override
)

print(result["kernel_result"])   # {"status": "committed", "root_hash": "..."}
print(result["audit_receipt"])   # {"root_hash": "...", "payload_hash": "...", ...}
```

---

## Configuration

All parameters are set in `AuditConfig`:

```python
from idicoc_audit_flow.config import AuditConfig

config = AuditConfig(
    # Core
    audit_mode="mathematical",          # "mathematical" | "semantic"
    rigidity_epsilon=0.0,               # manifold size; 0.0=factual, 0.7=creative
    source_name="ai_comercial",         # identifier for this AI instance
    constant_k="k",                     # invariant anchor constant

    # Thresholds
    isg_delta_fp=0.15,                  # ISG canonical state collapse tolerance
    correction_base_tolerance=0.15,     # DQE correction trigger threshold
    context_axiom_conflict_threshold=0.5,
    contradiction_snapping_threshold=0.5,

    # CTM persistence mode
    ctm_mode="full",                    # "full" | "log_only" | "disabled"

    # Mathematical strategy
    mathematical_weights=(0.15, 0.15, 0.15, 0.15, 0.14, 0.13, 0.13),
    mathematical_embedding_model=None,  # optional: sentence-transformers model

    # Semantic strategy
    semantic_embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    semantic_nli_model="facebook/bart-large-mnli",
    semantic_max_rag_results=5,
    semantic_min_rag_score=0.1,

    # Input field mapping (for process_dict)
    input_field_audit="audit_input",
    input_field_context="context_input",
    input_field_axioms="context_axioms",

    # Misc
    validate_context_against_axioms=False,
    extra_metadata={},
)
```

### `rigidity_epsilon` — creativity control

| Value | Behaviour |
|---|---|
| `0.0` | Factual mode — only responses very close to the invariant are accepted without correction. |
| `0.35` | Hybrid mode — moderate deviation allowed. |
| `0.7` | Creative mode — large freedom (hard axiom violations still recorded). |

> **Note**: the `mode` parameter (factual/hybrid/creative) has been removed. Use `rigidity_epsilon` directly.

---

## Persistence

IIAE supports three storage tiers:

### `ctm_mode`

| Mode | Behaviour |
|---|---|
| `"full"` | Full Merkle DAG and AEM persistence. Every interaction is cryptographically sealed. |
| `"log_only"` | No DAG writes. All commits and failures are emitted as structured JSON log lines (`iiae_data`). |
| `"disabled"` | Complete bypass. Zero overhead. Kernel and CTM are not invoked. |

### Storage backends

Implement `AEMStorageBackend` or `CTMStorageBackend` (defined in [`persistence/backend.py`](idicoc_audit_flow/persistence/backend.py)) to plug in any storage system (SQLite, S3, PostgreSQL, etc.).

The built-in `FileAEMStorage` and `FileCTMStorage` use plain JSON files with automatic directory creation.

---

## Audit Modes

### Mathematical (`audit_mode="mathematical"`)

A 7-component weighted dissonance score using:

1. Token frequency Manhattan distance
2. Sequence similarity ratio
3. Cosine distance (optional embedding model)
4. SHA-256 hash drift
5. Length ratio delta
6. Keyword overlap
7. Structural diff ratio

**No GPU or large model required.** Suitable for production environments with strict latency constraints.

### Semantic (`audit_mode="semantic"`)

Uses two transformer models:

- **Encoder**: `sentence-transformers/all-MiniLM-L6-v2` (configurable) — cosine distance between source and context embeddings.
- **NLI**: `facebook/bart-large-mnli` (configurable) — contradiction probability between source and each axiom.

`D_s = sup(max_cosine_distance, max_nli_contradiction)` — the worst-case geometric or logical deviation.

> Requires `sentence-transformers`, `transformers`, and `torch`. Download models with `python download_models.py` (requires `HF_TOKEN` in `.env`).

---

## Logging

IIAE emits structured JSON audit logs via the `IIAE.*` logger namespace.

```python
from idicoc_core.runtime.config import RuntimeConfig
RuntimeConfig(..., log_destination="stdout")   # default
```

| `log_destination` | Output |
|---|---|
| `"stdout"` | JSON lines to standard output |
| `"file:/path/to/audit.log"` | JSON lines to a file (auto-creates directories) |
| `"none"` | Silent (NullHandler) |
| `"azure"` | Azure Monitor (requires `opencensus-ext-azure` + `AZURE_LOG_CONNECTION_STRING`) |
| `"splunk"` | Splunk HEC (requires `splunk-handler` + `SPLUNK_HOST`, `SPLUNK_TOKEN`) |
| `"elastic"` | Elasticsearch (requires `CMRESHandler` + `ELASTIC_HOST`) |
| `"datadog"` | Datadog (requires `datadog` + `DD_API_KEY`) |
| `"siem"` | Syslog (requires `SIEM_SYSLOG_HOST`) |

Every log record includes `timestamp`, `level`, `module`, `message`, and optional `iiae_data` fields for forensic detail.

---

## Testing

```bash
# Run all tests
PYTHONPATH=. pytest tests/ -v

# Run only wrapper tests
PYTHONPATH=. pytest tests/test_idicoc_wrapper.py -v

# Run only persistence tests
PYTHONPATH=. pytest tests/test_persistence.py -v
```

Current test coverage:

| Test | Description |
|---|---|
| `test_audit_config_properties` | AuditConfig defaults and field validation |
| `test_invariant_state_generator_delta_fp` | ISG canonical state projection |
| `test_semantic_strategy_compute` | Semantic dissonance scoring |
| `test_mathematical_strategy_compute` | Mathematical dissonance scoring |
| `test_pipeline_exception_handling` | Graceful fallback on pipeline errors |
| `test_semantic_supremum_single_critical_axiom` | NLI contradiction supremum |
| `test_pipeline_algebraic_components_in_metadata` | Coalgebraic component verification |
| `test_verify_compliance_algebraic_validation` | `verify_compliance` algebraic checks |
| `test_aem_file_persistence` | AEM JSON file backend round-trip |
| `test_ctm_file_persistence` | CTM node/root hash file backend round-trip |
| `test_pipeline_with_persistence` | End-to-end pipeline with disk persistence and DAG reload |
| `test_ctm_modes` | `log_only` and `disabled` mode behaviour |

---

## Requirements

**Core** (always required):

```
numpy
scipy>=1.8.0
pandas
python-dotenv
pytest
```

**Semantic mode** (optional):

```
sentence-transformers
transformers
torch
scikit-learn
sentencepiece
```

**Hugging Face token**: add `HF_TOKEN=<your_token>` to `.env` if downloading gated models.

---

## Project Structure

```
IIAE/
├── idicoc_audit_flow/          # Public SDK layer
│   ├── config.py               # AuditConfig
│   ├── base.py                 # CanonicalStateDTO, EntropyAnalyzer, IDICOCWrapperContract
│   ├── wrapper_pipeline.py     # IDICOCWrapper (main entry point)
│   ├── pipeline.py             # IIAEEnterpriseSDKWrapper (orchestrator)
│   ├── kernel_client.py        # KernelCustodyClient
│   ├── axioms.py               # AxiomEngine
│   ├── exceptions.py           # SDK exceptions
│   ├── strategies/
│   │   ├── mathematical.py     # MathematicalDissonanceStrategy
│   │   └── semantic.py         # SemanticDissonanceStrategy
│   └── persistence/
│       ├── backend.py          # Abstract storage interfaces
│       └── file_backend.py     # JSON file implementation
│
├── idicoc_core/                # Deterministic engine (domain-independent)
│   ├── runtime/config.py       # RuntimeConfig — system assembly
│   └── core/
│       ├── admission/aem.py    # AnomalousEventManager
│       ├── custody/merkle_dag.py # MerkleDAG, CustodialTraceManager
│       ├── pipeline/kernel.py  # CustodialKernel (7-stage pipeline)
│       ├── projection/         # InvariantStateGenerator
│       ├── manifold/cmc.py     # ManifoldConstructor
│       ├── deviation/dqe.py    # DeviationQuantifier
│       ├── dse/dse.py          # DynamicSchemaExtractor
│       ├── verification/       # InvariantVerifier
│       ├── graph/              # PropertyGraph
│       └── source/             # SourceAnchor
│
├── idicoc_utils/               # Shared utilities
│   ├── logger.py               # JSON audit logger
│   └── hashing.py              # SHA-256, HMAC, canonical JSON
│
├── tests/
│   ├── test_idicoc_wrapper.py
│   └── test_persistence.py
│
├── requirements.txt
└── pyproject.toml
```

---

## License

See [LICENSE](LICENSE) and [LICENSE.md](LICENSE.md) for terms.  
See [NOTICE](NOTICE) for third-party attributions.  
See [SECURITY.md](SECURITY.md) for vulnerability reporting guidelines.
