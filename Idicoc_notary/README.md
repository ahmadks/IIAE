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

### Glosario de Emergencia para Producción (3:00 AM)

Si estás despierto a las 3:00 AM intentando descifrar una alerta de producción, aquí tienes la traducción de los términos académicos a lenguaje de ingeniería:

*   **SourceAnchor (Attractor K / Ancla de Referencia):** Es un vector matemático fijo e inmutable que representa el "estado ideal o perfecto". Se usa como base absoluta para comparar cualquier desviación.
*   **InvariantStateGenerator (ISG / Generador de Estado Invariante):** Toma el texto de entrada y lo traduce a un vector numérico (su embedding semántico). Si el vector está muy cerca de nuestro estado de referencia (`SourceAnchor`) por debajo del umbral de tolerancia `isg_delta_fp`, lo fuerza (colapsa) a ser exactamente igual al de referencia para evitar ruidos acumulados o variaciones numéricas sutiles.
*   **AuditEntropyModule (AEM / Contador de Admisiones):** Funciona como el portero del flujo de auditoría: lleva la cuenta exacta de cuántas solicitudes son aprobadas (admisiones), cuántas son bloqueadas (rechazos) y registra un historial forense (`audit_trail_map`) con los motivos específicos del rechazo.
*   **StructuralDissonanceStrategy (SPSA / Corrección sin Gradientes):** Algoritmo iterativo sumamente veloz que optimiza y proyecta (corrige) las respuestas de la IA hacia una zona permitida si estas superan los límites de desviación, protegiendo el sistema sin sobrecargar la CPU.

---

### Flujo de Datos Simplificado

El siguiente diagrama detalla cómo fluye una petición de auditoría y dónde intervienen las etapas coalgebraicas y criptográficas:

```text
               [ Entrada de Auditoría (Texto / Datos) ]
                                  │
                                  ▼
                [ InvariantStateGenerator (ISG) ]
                 Convierte a vector y estabiliza
                                  │
                                  ▼
               [ DSE & DissonanceCalculator (DQE) ]
          Mide desviación (D_s) contra el Ancla de Referencia
                                  │
                 ¿D_s <= Rigidity Epsilon (Tolerancia)?
                 /                                  \
             (Sí)                                  (No)
              /                                      \
             ▼                                        ▼
    [ Admitida Directa ]                   [ ManifoldConstructor (CMC) ]
                                        Corrige vector vía SPSA si es posible
                                                      │
                                             ¿Corrección exitosa?
                                             /                  \
                                         (Sí)                  (No)
                                          /                      \
                                         ▼                        ▼
                              [ Admitida Con Corrección ]    [ Rechazada ]
                                         \                        /
                                          ▼                      ▼
                                       [ AuditEntropyModule (AEM) ]
                                        Registra admisiones / rechazos
                                                      │
                                                      ▼
                                       [ CustodialTraceManager (CTM) ]
                                      Sella inmutablemente en el Merkle DAG
```

---

### Guía Operativa de Emergencia: "Qué hacer a las 3:00 AM"

Si recibes una alerta de producción de este servicio durante la noche, sigue esta lista de diagnóstico rápida:

1.  **¿Se están rechazando todas las peticiones?**
    *   Revisa los contadores del **AEM** (`aem_counters` en las respuestas). Si `rejected_signals` está subiendo de forma exponencial, es muy probable que el modelo de la IA haya empezado a generar respuestas inconsistentes o alucinadas que violan los axiomas de negocio configurados.
    *   Verifica si se ha inyectado un archivo de axiomas corrupto o restrictivo (`axioms.txt`).
2.  **¿Fallo de Firma de Embeddings (`strict_embedding_signature` activo)?**
    *   Si el servicio no arranca y lanza un error sobre la firma del modelo de embeddings, significa que alguien cambió el modelo configurado (ej. de `all-MiniLM-L6-v2` a otro) en `AuditConfig` pero el modo estricto está habilitado.
    *   **Solución:** Valida si el cambio de modelo fue planificado. Si es correcto, actualiza `embedding_signature` en la configuración con la firma correcta.
3.  **¿Fallo de Conexión de Persistencia CTM (`psycopg2`, `boto3`, `pyqldb`)?**
    *   En modo estricto (`mock=False`), el pipeline lanzará un `PersistenceError` si pierde conexión con la base de datos (PostgreSQL, DynamoDB o QLDB).
    *   **Solución:** Comprueba las credenciales, la cadena de conexión en `ctm_postgres_uri` / `ctm_storage_kwargs` y el estado de salud de la base de datos de destino. Si estás en desarrollo local, puedes configurar temporalmente `mock=True` en `ctm_storage_kwargs` para aislar el error de infraestructura.
4.  **¿Explosión de Cómputo por Texto Gigante?**
    *   Si detectas latencias extremas o cuellos de botella de CPU/Memoria, es probable que un usuario haya enviado un documento de texto masivo. Nuestro mecanismo limita esto a `embedding_max_chunks` (por defecto 10 chunks). Si se excede, lanzará un `ValueError` claro para proteger el pod de producción.

---

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
<!-- | `hardware_key_env_var` | `str` | `IIAE_HARDWARE_KEY` | Env variable for hardware seal key | -->
<!-- | `require_hardware_seal` | `bool` | `False` | Fail if hardware key is absent | -->
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
