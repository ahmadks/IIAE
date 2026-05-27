# IDICOC Notary Core

**Invariant Deterministic Identity Chain of Custody** — an audit SDK for AI systems grounded in coalgebraic mathematics and cryptographic ledger anchoring.

`idicoc-notary-core` enforces structural determinism over AI inference traces. Every output is scored against a 7-stage coalgebraic metric, admitted or rejected by a multi-criteria forensic filter matrix, and sealed into a tamper-evident Merkle custody log.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Public API](#public-api)
- [Package Structure](#package-structure)
- [Testing](#testing)

---

## Overview

The framework implements the **MAII** (*Motor de Auditoría de Integridad Invariante*) as described in the IDICOC-DSE specification. Its core guarantees are:

- **Structural Dissonance Scoring** — every inference trace is measured against a canonical attractor *K* using the 7-component metric *D*s = Σ λᵢ · dᵢ.
- **Coinductive Gating** — traces with a local Lipschitz constant *L ≥ 1* are sandboxed; traces with *L < 1* propagate to the ledger.
- **Cryptographic Custody** — admitted traces are committed to a Merkle DAG, optionally sealed with hardware-derived keys.
- **Axiom Enforcement** — an injectable `AxiomLoader` ensures that logical invariants are parsed and strictly evaluated per session without graph pollution.

---

## Architecture

```
IDICOCNotaryClient          ← public entry-point (IIAENotaryContract)
    └── IDICOCPipeline      ← linear orchestrator (7-stage coalgebraic pipeline)
            ├── SourceAnchor            (S₀) identity constant / attractor K
            ├── InvariantStateGenerator (S₁) canonical embedding
            ├── AxiomExtractor          (S₂) static context/axiom precomputation into PropertyGraph
            ├── DissonanceCalculator    (S₃–S₄) D_s computation via DissonanceStrategy
            │       └── StructuralDissonanceStrategy   ← SPSA-optimised convex metric
            ├── ManifoldConstructor     (S₄) geometric sandboxing / Lipschitz gate
            ├── AuditEntropyModule      (S₅) admission counters y_valid / n_t
            └── CustodialTraceManager   (S₆) Merkle DAG + hardware seal
```

### Key Design Decisions

| Concern | Solution |
|---|---|
| Kernel ↔ Audit coupling | `DissonanceCalculator` depends on the abstract `DissonanceStrategy`, not the concrete implementation |
| Cryptographic integrity | AEM counters are committed *before* CTM sealing so every Merkle node includes `(y_valid, n_t)` |
| SPSA optimisation | `StructuralDissonanceStrategy.project` uses Simultaneous Perturbation Stochastic Approximation to optimise *D*s multi-objective |
| Entropy injection | `AuditEntropyModule` tracks admission / rejection counters independent of session state |

---

## Installation

```bash
# From the Idicoc_notary directory
pip install -e ".[dev]"
```

**Requirements**: Python ≥ 3.10, numpy, scipy, pandas, sentence-transformers, torch, scikit-learn.

---

## Quick Start

```python
from idicoc_notary_core import IDICOCNotaryClient, AuditConfig

config = AuditConfig(
    instance_name="my_ai_service",
    ctm_mode="full",               # "full" | "hash_only" | "disabled"
    dissonance_weights=(0.0, 0.5, 0.4, 0.1, 0.0, 0.0, 0.0),
)

client = IDICOCNotaryClient(config)

result = client.audit(
    audit_input="The output to be audited.",
    context=["reference context A", "reference context B"],
    axioms=["Axiom: outputs must not contradict source."],
)

print(result.is_admitted)       # True / False
print(result.dissonance_score)  # float in [0, 1]
print(result.ctm_node_hash)     # Merkle node SHA-256
```

---

## Configuration

`AuditConfig` (dataclass) — all fields have sensible defaults:

| Field | Type | Default | Description |
|---|---|---|---|
| `instance_name` | `str` | `"ai_comercial"` | Identifier for this audit source |
| `ctm_mode` | `str` | `"full"` | Custody mode: `full`, `hash_only`, `disabled` |
| `dissonance_weights` | `tuple[float, ...]` | `(0,0.5,0.4,0.1,0,0,0)` | λ₀…λ₆ must sum to 1 |
| `isg_delta_fp` | `float` | `0.15` | Fixed-point tolerance for InvariantStateGenerator |
| `embedding_signature` | `str | None` | `None` | Expected SHA-256 signature for the model |
| `strict_embedding_signature`| `bool` | `False` | Fails fast if model signature does not match |
| `rigidity_epsilon` | `float` | `1e-6` | Threshold for Lipschitz contractivity gate |
| `ctm_nodes_path` | `str` | `Idicoc_notary/tests/results/ctm_nodes.json` | Path for Merkle node storage |
| `ctm_root_path` | `str` | `ctm_root.txt` | Path for Merkle root anchor |
| `hardware_key_env_var` | `str` | `IIAE_HARDWARE_KEY` | Env variable for hardware seal key |
| `require_hardware_seal` | `bool` | `False` | Fail if hardware key is absent |
| `axiom_loader` | `AxiomLoader` | `None` | Dependency injected loader instance |
| `axiom_file_path` | `str` | `"axioms.txt"` | Fallback path if loader is `None` |

---

## Public API

All public symbols are re-exported from the top-level package:

```python
from idicoc_notary_core import (
    IDICOCNotaryClient,       # High-level client (IIAENotaryContract)
    IDICOCPipeline,           # Low-level pipeline orchestrator
    AuditConfig,              # Configuration dataclass
    AxiomLoader,              # Protocol for external axiom loading
    FileAxiomLoader,          # Concrete loader for text/JSON files
    InlineAxiomLoader,        # Concrete loader for testing / memory
    GraphCache,               # Protocol for PropertyGraph caching
    RedisGraphCache,          # Distributed redis cache implementation
    CanonicalStateDTO,        # Result/state data transfer object
    KernelCustodyClient,      # Direct CTM interface
    DissonanceStrategy,       # Abstract base for custom strategies
    WrapperInitializationError,
)
```

### Implementing a Custom Strategy

```python
from idicoc_notary_core import DissonanceStrategy, AuditConfig
from typing import Any, Dict, List, Tuple

class MyStrategy(DissonanceStrategy):
    def __init__(self, config: AuditConfig) -> None:
        super().__init__(config)

    def compute(
        self,
        audit_input: Any,
        context_input: List[str],
        context_axioms: List[str],
        epsilon: float = 0.0,
        validate_conflicts: bool = False,
    ) -> Tuple[float, float, Any, bool, Dict[str, Any]]:
        # Return (D_s, D_f, corrected_output, correction_flag, metrics_dict)
        ...

    def select_canonical_input(self, canonical_state: Any) -> Any: ...
    def canonical_axis(self) -> str: return "semantic"
```

Pass the strategy to `AuditConfig` or inject it directly into `IDICOCPipeline`.

---

## Package Structure

```
idicoc_notary_core/
├── __init__.py                    # Top-level public exports
│
├── audit/                         # Orchestration & public interface layer
│   ├── __init__.py
│   ├── pipeline.py                # IDICOCPipeline — 7-stage linear orchestrator
│   ├── wrapper_pipeline.py        # IDICOCNotaryClient — public API adapter
│   ├── config.py                  # AuditConfig dataclass
│   ├── aem.py                     # AuditEntropyModule (y_valid / n_t counters)
│   ├── base.py                    # CanonicalStateDTO, IIAENotaryContract
│   ├── exceptions.py              # ComplianceBreach, WrapperInitializationError
│   ├── ctm_client.py              # KernelCustodyClient
│   ├── graph/                     # Graph management and context
│   │   ├── property_graph_evaluator.py # Evaluation logic
│   │   ├── cache/                 # Distributed caching (NoOp, Redis)
│   │   └── loader/                # Axiom loaders (File, Inline)
│   ├── dse/                       # Dissonance Strategy Engine
│   │   ├── __init__.py
│   │   ├── dissonance_strategy.py # Abstract base DissonanceStrategy
│   │   └── structural_strategy.py # StructuralDissonanceStrategy (SPSA, D_s)
│   └── persistence/
│       ├── __init__.py
│       ├── backend.py             # CTMStorageBackend protocol
│       └── file_backend.py        # FileCTMStorage
│
└── kernel/                        # Core mathematical / cryptographic primitives
    ├── __init__.py
    ├── admission/                 # Admission gate logic
    ├── custody/
    │   └── merkle_dag.py          # MerkleDAG, CustodialTraceManager, EnvHardwareSealer
    ├── deviation/
    │   └── dqe.py                 # DissonanceCalculator (coalgebraic D_s engine)
    ├── dse/
    │   └── dse.py                 # AxiomExtractor (PropertyGraph updater)
    ├── graph/
    │   └── property_graph.py      # PropertyGraph (context + axiom store)
    ├── manifold/
    │   └── cmc.py                 # ManifoldConstructor (Lipschitz gate / sandbox)
    ├── pipeline/
    │   └── kernel.py              # CustodialKernel
    ├── projection/
    │   └── invariant_state_generator.py  # InvariantStateGenerator, CanonicalState
    ├── source/
    │   └── anchor.py              # SourceAnchor (attractor K)
    ├── verification/
    │   ├── registry.py            # ProjectionRegistry
    │   └── verifier.py            # InvariantVerifier
    └── utils/
        ├── hashing.py             # canonical_json, sha256_hex, sha256_dict
        └── logger.py              # get_logger, configure_logging
```

---

## Testing

```bash
cd Idicoc_notary
pytest tests/ -v --tb=short
```

The test suite covers:
- `test_IIAEService_logic.py` — pipeline admission / rejection with logic axioms
- `test_IIAEService_semantic.py` — semantic embedding dissonance scenarios
- `test_structural_dissonance_strategy.py` — SPSA projection, D_s computation, pipeline graph integration
- `test_logic_strategy.py` — structural strategy unit tests
- `test_axiom_loader.py` — testing file and inline axiom loading
- `test_pipeline_loader.py` — pipeline initialization and strictly read-only execution graph

All 44 tests pass efficiently due to the `EmbeddingService` singleton minimizing redundant model loads.

---

## License

MIT © IIAE Contributors
