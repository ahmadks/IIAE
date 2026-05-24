# IIAE & IDICOC Notary: Audit Framework for AI Systems

## Overview

**IIAE** (Intelligent Invariant Audit Engine) is a comprehensive SDK for auditing AI systems with deterministic consensus and cryptographic trazability. **IDICOC Notary Core** provides the deterministic kernel that enforces invariant-based compliance through a 7-stage coalgebraic pipeline.

This framework acts as a **notary**: it measures, classifies, and records AI system behavior without blocking or rejecting outputs. The notary never modifies the AI's operational flow—it only audits and seals evidence.

## Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Quick Start](#quick-start)
5. [Core Concepts](#core-concepts)
6. [Configuration](#configuration)
7. [Usage Examples](#usage-examples)
8. [Module Reference](#module-reference)
9. [Contributing](#contributing)
10. [License](#license)

---

## Features

- **Deterministic Audit Pipeline**: Reproducible, cryptographically sealed audit traces
- **Invariant-Based Compliance**: Define hard constraints (axioms) and measure deviation (disonancia)
- **Dual Dissonance Strategies**: 
  - **Semantic**: NLI-based contradiction detection with embeddings
  - **Mathematical**: Token/frequency-based distance metrics
- **Merkle DAG Custody**: Cryptographic proof of audit chain integrity
- **Notarial Passivity**: Never blocks or rejects outputs—only measures and records
- **Flexible Creativity Control**: Adjust manifold size via `rigidity_epsilon` parameter
- **Python 3.10+**: Modern Python with strong typing

---

## Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      IIAEService (Wrapper)                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Input Adaptation & Field Mapping (IDICOCWrapperContract)│  │
│  └───────────────────────────────────────────────────────────┘  │
│                            ▼                                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │        IIAEServiceAuditor (Orchestrator)                 │  │
│  │  • Axiom Engine (PropertyGraph)                           │  │
│  │  • Dissonance Strategy Selection                          │  │
│  │  • Kernel Factory                                         │  │
│  └───────────────────────────────────────────────────────────┘  │
│                            ▼                                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │    CustodialKernel (7-Stage Pipeline)                    │  │
│  │  1. Admission (AEM)         → Noise Segregation          │  │
│  │  2. Projection (ISG)        → Canonical State            │  │
│  │  3. Schema (DSE)            → Graph Update               │  │
│  │  4. Manifold (CMC)          → Admissible Region          │  │
│  │  5. Deviation (DQE)         → Dissonance Score           │  │
│  │  6. Correction              → Optional Projection        │  │
│  │  7. Verification (Verifier) → Alignment Check            │  │
│  │  ▼ Custody (CTM)            → Merkle Sealing             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                            ▼                                     │
│              CanonicalStateDTO (Sealed Audit)                    │
│           Immutable • Hash-Verified • Trazable                   │
└─────────────────────────────────────────────────────────────────┘
```

### Directory Structure

```
IIAE/
├── Idicoc_notary/                      # Main package
│   ├── pyproject.toml                  # Package metadata
│   ├── idicoc_notary_core/
│   │   ├── __init__.py                 # Public API exports
│   │   ├── audit/
│   │   │   ├── __init__.py             # Audit module exports
│   │   │   ├── base.py                 # Core contracts & DTOs
│   │   │   ├── config.py               # AuditConfig dataclass
│   │   │   ├── axioms.py               # AxiomEngine
│   │   │   ├── pipeline.py             # IIAEServiceAuditor
│   │   │   ├── wrapper_pipeline.py     # IIAEService
│   │   │   ├── kernel_client.py        # KernelCustodyClient
│   │   │   ├── exceptions.py           # Custom exceptions
│   │   │   ├── README.md               # Audit module docs
│   │   │   ├── persistence/            # Storage backends
│   │   │   │   ├── backend.py
│   │   │   │   └── file_backend.py
│   │   │   └── strategies/             # Dissonance strategies
│   │   │       ├── base.py             # Abstract DissonanceStrategy
│   │   │       ├── mathematical.py     # Token-based strategy
│   │   │       └── semantic.py         # NLI-based strategy
│   │   ├── kernel/                     # Deterministic core
│   │   │   ├── admission/
│   │   │   │   └── aem.py              # AnomalousEventManager
│   │   │   ├── custody/
│   │   │   │   └── merkle_dag.py       # MerkleDAG + CTM
│   │   │   ├── deviation/
│   │   │   │   └── dqe.py              # DeviationQuantifier
│   │   │   ├── dse/
│   │   │   │   └── dse.py              # DynamicSchemaExtractor
│   │   │   ├── exceptions/
│   │   │   │   ├── alignment_breach.py
│   │   │   │   └── integrity_breach.py
│   │   │   ├── graph/
│   │   │   │   └── property_graph.py   # PropertyGraph (axiom store)
│   │   │   ├── manifold/
│   │   │   │   └── cmc.py              # ManifoldConstructor
│   │   │   ├── pipeline/
│   │   │   │   └── kernel.py           # CustodialKernel
│   │   │   ├── projection/
│   │   │   │   └── invariant_state_generator.py  # ISG
│   │   │   ├── source/
│   │   │   │   └── anchor.py           # SourceAnchor
│   │   │   └── verification/
│   │   │       ├── registry.py         # ProjectionRegistry
│   │   │       └── verifier.py         # InvariantVerifier
│   │   └── utils/
│   │       ├── hashing.py              # SHA256, canonical JSON
│   │       └── logger.py               # Logging utilities
│   ├── tests/
│   │   ├── test_idicoc_wrapper.py      # Integration tests
│   │   └── test_persistence.py         # Persistence tests
│   └── requirements.txt                # Sub-package dependencies
├── SLT/                                # Separate module
│   ├── __init__.py
│   ├── SLT_pyTest.py
│   └── SLT_Standard_Zero.py
├── pyproject.toml                      # Root project config
├── requirements.txt                    # Root dependencies
├── download_models.py                  # Model cache helper
├── IIAE_IDICOC-DSE.pdf                 # Technical specification
├── README.md                           # This file
└── LICENSE                             # MIT License
```

---

## Installation

### Prerequisites
- Python 3.10 or higher
- pip or conda

### From Source

```bash
# Clone the repository
git clone <repository-url>
cd IIAE

# Install IDICOC Notary Core
cd Idicoc_notary
pip install -e .

# Install optional dependencies for semantic audit
pip install -e ".[dev]"  # For development & testing
```

### Via pip (if published)

```bash
pip install idicoc-notary-core
```

### Model Download (Optional)

For semantic dissonance strategy, download pre-trained models:

```bash
python download_models.py
```

This caches embedding and NLI models locally for offline use.

---

## Quick Start

### Basic Audit with Semantic Strategy

```python
from idicoc_notary_core.audit import (
    AuditConfig,
    IIAEService,
    BankEntropyAnalyzer,
)

# 1. Configure audit mode
config = AuditConfig(
    audit_mode="semantic",
    rigidity_epsilon=0.35,  # Hybrid mode (some creativity allowed)
    source_name="ai_chatbot_v1",
    semantic_embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    semantic_nli_model="facebook/bart-large-mnli",
)

# 2. Create entropy analyzer (domain-specific)
entropy_analyzer = BankEntropyAnalyzer()  # or custom implementation

# 3. Initialize audit service
audit_service = IIAEService(config, entropy_analyzer)

# 4. Define axioms (hard constraints)
axioms = [
    {"id": "a1", "text": "Cannot discuss personal banking details", "polarity": True},
    {"id": "a2", "text": "Must maintain professional tone", "polarity": True},
]

# 5. Audit an AI response
response = "The balance is $5000 and credit is good."
context = ["User asked for balance", "User is authenticated"]
axiom_texts = ["Cannot discuss personal banking details"]

canonical_state = audit_service.process_interaction(
    audit_input=response,
    context_input=context,
    context_axioms=axiom_texts,
    epsilon_override=0.35,
)

# 6. Verify compliance
is_compliant = audit_service.verify_compliance(canonical_state, tolerance=0.35)

# 7. Inspect audit trail
print(f"Dissonance Score (D_s): {canonical_state.metadata['d_s']}")
print(f"Final Output: {canonical_state.metadata.get('final_output')}")
print(f"Timestamp: {canonical_state.timestamp}")
print(f"Integrity Hash: {canonical_state.integrity_hash}")
print(f"Compliant: {is_compliant}")
```

### Basic Audit with Mathematical Strategy

```python
from idicoc_notary_core.audit import AuditConfig, IIAEService, BankEntropyAnalyzer

config = AuditConfig(
    audit_mode="mathematical",
    rigidity_epsilon=0.0,  # Factual mode
    mathematical_weights=(0.15, 0.15, 0.15, 0.15, 0.14, 0.13, 0.13),
)

entropy_analyzer = BankEntropyAnalyzer()
audit_service = IIAEService(config, entropy_analyzer)

canonical_state = audit_service.process_interaction(
    audit_input="Response text",
    context_input=["Context chunk 1"],
    context_axioms=["Axiom 1"],
)

is_compliant = audit_service.verify_compliance(canonical_state)
print(f"Audit Result: D_s={canonical_state.metadata['d_s']}, Compliant={is_compliant}")
```

---

## Core Concepts

### 1. Disonancia (D_s)

**Disonancia** measures how much an AI output deviates from the invariant state defined by axioms.

**Formula:**
```
D_s = λ_inv × d_inv + λ_logic × d_logic + λ_temporal × d_temp

Where:
  λ_inv = 0.5      (structural/invariant component weight)
  λ_logic = 0.4    (axiom violation weight)
  λ_temporal = 0.1 (temporal consistency weight)
```

**Interpretation:**
- D_s ≈ 0: Output perfectly aligns with axioms (highly constrained)
- D_s ≈ 0.35: Hybrid mode (some creative latitude allowed)
- D_s ≈ 1.0: Output violates multiple axioms (coherent hallucination detected)

### 2. Axioms

Axioms are **hard constraints** defined in the `PropertyGraph`. They prevent coherent hallucinations.

**Example Axioms (Banking Domain):**
```python
axioms = [
    {
        "id": "ax_privacy",
        "text": "Never disclose customer SSN without explicit authorization",
        "polarity": True,  # Must always be satisfied
    },
    {
        "id": "ax_professionalism",
        "text": "Maintain professional tone in all customer interactions",
        "polarity": True,
    },
]
```

**Axiom Verification:**
1. **Policy Axioms**: Injected at initialization (global policy)
2. **Context Axioms**: Provided per-request (session-specific)
3. **Conflict Detection**: PropertyGraph detects opposite-polarity axioms

### 3. Rigidity Epsilon (ε)

Controls the **manifold size**—the region of acceptable outputs around the invariant.

**Modes:**
- **ε = 0.0** (Factual): Only responses identical/near-identical to invariant
- **ε = 0.35** (Hybrid): Allows creative variation while respecting axioms
- **ε = 0.7** (Creative): Maximum freedom; only hard axioms enforced

**Usage:**
```python
# Set globally
config = AuditConfig(rigidity_epsilon=0.35)

# Override per-request
audit_service.process_interaction(
    audit_input="...",
    epsilon_override=0.5,  # Temporarily more creative
)
```

### 4. CanonicalStateDTO

Immutable audit state produced by the kernel.

**Fields:**
```python
@dataclass(frozen=True)
class CanonicalStateDTO:
    data: Any                            # Normalized AI output
    metadata: dict[str, Any]             # Audit metrics (D_s, D_f, timestamps, etc.)
    source_axioms: list[str]             # Axioms used in this audit
    integrity_hash: str                  # SHA256 verification hash
    timestamp: str                       # ISO 8601 timestamp
```

**Metadata Includes:**
- `d_s`: Disonancia score
- `d_f`: Final dissonance
- `audit_mode`: Strategy used (semantic/mathematical)
- `correction_flag`: Whether correction was applied
- `algebraic_components`: λ weights and d_logic for coalgebraic verification
- `violated_axioms`: List of breached constraints
- `support_found`: Whether context supported the output

### 5. Entropy Analyzer

Abstract interface for measuring input entropy (domain-specific implementation).

```python
class EntropyAnalyzer(Protocol):
    def measure_entropy(self, raw_input: Any) -> float:
        """Returns normalized value in [0, 1]."""
        ...
    
    def decompose(self, raw_input: Any) -> tuple[Any, Any]:
        """Split into structural component and noise."""
        ...
    
    def is_recoverable(self, noise: Any) -> bool:
        """Determine if noise can be recovered."""
        ...
```

**Example: BankEntropyAnalyzer**
```python
class BankEntropyAnalyzer:
    def measure_entropy(self, raw_input: Any) -> float:
        # Count non-alphanumeric characters
        text = str(raw_input)
        non_alpha = sum(1 for c in text if not c.isalnum() and not c.isspace())
        return min(1.0, non_alpha / max(1, len(text)))
    
    def decompose(self, raw_input: Any) -> tuple[str, Any]:
        # Extract account numbers as noise
        text = str(raw_input)
        structural = re.sub(r"\b\d{10,}\b", "[ACCOUNT]", text)
        noise = re.findall(r"\b\d{10,}\b", text)
        return structural, noise
    
    def is_recoverable(self, noise: Any) -> bool:
        return bool(noise)
```

### 6. Dissonance Strategies

#### Semantic Strategy (NLI-Based)

Uses embedding models and Natural Language Inference (NLI) to detect contradiction.

**Process:**
1. Encode audit input, axioms, context into embeddings
2. Compute cosine distance between vectors
3. Apply NLI model to detect explicit contradiction
4. Measure support: does context support the output?
5. Quantify d_logic: ratio of violated axioms

**Config:**
```python
config = AuditConfig(
    audit_mode="semantic",
    semantic_embedding_model="sentence-transformers/all-MiniLM-L6-v2",
    semantic_nli_model="facebook/bart-large-mnli",
    semantic_max_rag_results=5,
    semantic_min_rag_score=0.1,
)
```

**Advantages:**
- Detects nuanced contradictions (not just exact matches)
- Understands synonymy and paraphrasing
- Robust to minor rewording

#### Mathematical Strategy (Token-Based)

Uses frequency analysis, embedding distance, and hash comparison.

**Process:**
1. Compute token frequency dictionaries
2. Calculate Manhattan distance between frequencies
3. Apply embedding cosine distance (if embedder provided)
4. Measure JSON/structural validity
5. Compare hashes against expected values

**Config:**
```python
config = AuditConfig(
    audit_mode="mathematical",
    mathematical_weights=(0.15, 0.15, 0.15, 0.15, 0.14, 0.13, 0.13),
    mathematical_embedding_model=None,  # Optional
)
```

**Advantages:**
- Deterministic and fast
- No neural model required (offline capability)
- Sensitive to exact structural changes
- Good for code/JSON audit

---

## Configuration

### AuditConfig Reference

```python
@dataclass
class AuditConfig:
    # Strategy selection
    audit_mode: Literal["semantic", "mathematical"] = "semantic"
    
    # Tolerances & thresholds
    isg_delta_fp: float = 0.15                          # ISG collapse threshold
    correction_base_tolerance: float = 0.15             # DQE correction trigger
    context_axiom_conflict_threshold: float = 0.5       # Conflict detection threshold
    contradiction_snapping_threshold: float = 0.5       # Factual snapping trigger
    
    # Manifold control
    rigidity_epsilon: float = 0.0  # 0.0=factual, 0.35=hybrid, 0.7=creative
    constant_k: Any = "k"                               # Terminal coalgebra identity
    
    # Identification
    source_name: str = "ai_comercial"                   # Service instance name
    
    # Semantic mode parameters
    semantic_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    semantic_nli_model: str = "facebook/bart-large-mnli"
    semantic_max_rag_results: int = 5
    semantic_min_rag_score: float = 0.1
    
    # Mathematical mode parameters
    mathematical_weights: tuple[float, ...] = (0.15, 0.15, 0.15, 0.15, 0.14, 0.13, 0.13)
    mathematical_embedding_model: str | None = None
    
    # Validation
    validate_context_against_axioms: bool = False       # Check for conflicts
    
    # Custody mode
    ctm_mode: Literal["full", "log_only", "disabled"] = "full"
    enable_hard_halt: bool = False  # Force False (notary doesn't block)
    
    # Optional tracing
    client_id: str | None = None
    trace_input: str | None = None
    
    # Field mapping
    input_field_audit: str = "audit_input"
    input_field_context: str = "context_input"
    input_field_axioms: str = "context_axioms"
    
    # Extra metadata
    extra_metadata: dict[str, Any] = field(default_factory=dict)
```

### Environment Variables

```bash
# Hardware sealing key (for CTM custody)
export IIAE_HARDWARE_KEY="your-secret-key"

# Hugging Face token (for model downloads)
export HF_TOKEN="hf_..."

# Model cache directory (optional)
export HF_HOME="/path/to/cache"
```

---

## Usage Examples

### Example 1: Financial Compliance Audit

```python
from idicoc_notary_core.audit import (
    AuditConfig,
    IIAEService,
    BankEntropyAnalyzer,
)

# Configure for strict compliance
config = AuditConfig(
    audit_mode="semantic",
    rigidity_epsilon=0.0,  # Factual mode: strict
    source_name="fintech_api_v2",
    validate_context_against_axioms=True,
    ctm_mode="full",  # Full custody chain
)

# Initialize
analyzer = BankEntropyAnalyzer()
audit_service = IIAEService(config, analyzer)

# Define compliance axioms
axioms = [
    "Cannot disclose account balances without customer consent",
    "All transactions must be verified against transaction history",
    "Personal information (SSN, DOB) is never exposed",
]

# Audit response
ai_response = "Customer balance: $50,000 (verified from account 1234567890)"

result = audit_service.process_interaction(
    audit_input=ai_response,
    context_input=["Customer requested balance check"],
    context_axioms=axioms,
)

# Verify and log
if audit_service.verify_compliance(result):
    print("✓ COMPLIANT: Response meets all axioms")
else:
    print("✗ NON-COMPLIANT: Axiom violations detected")
    print(f"Violations: {result.metadata.get('violated_axioms')}")
```

### Example 2: Multi-Stage Audit with Context

```python
from idicoc_notary_core.audit import AuditConfig, IIAEService, BankEntropyAnalyzer

config = AuditConfig(
    audit_mode="semantic",
    rigidity_epsilon=0.35,  # Allow moderate creativity
    validate_context_against_axioms=True,
)

audit_service = IIAEService(config, BankEntropyAnalyzer())

# Define context (supporting documents)
context = [
    "User is authenticated as John Doe",
    "Last login: 2 hours ago from USA IP",
    "Account in good standing since 2020",
]

# Define axioms
axioms = [
    "Verify user identity before sharing account information",
    "Flag unusual access patterns",
]

# Audit multiple responses
responses = [
    "Your account balance is $10,000.",
    "No unusual activity detected.",
]

for response in responses:
    result = audit_service.process_interaction(
        audit_input=response,
        context_input=context,
        context_axioms=axioms,
    )
    
    print(f"Response: {response}")
    print(f"  D_s Score: {result.metadata['d_s']:.3f}")
    print(f"  Support Found: {result.metadata.get('support_found')}")
    print()
```

### Example 3: Custom Entropy Analyzer

```python
from idicoc_notary_core.audit.base import EntropyAnalyzer
from idicoc_notary_core.audit import AuditConfig, IIAEService
import re

class MedicalRecordAnalyzer:
    """Domain-specific entropy analysis for medical records."""
    
    def measure_entropy(self, raw_input: Any) -> float:
        text = str(raw_input)
        
        # Flag HIPAA-sensitive patterns
        ssn_pattern = r"\d{3}-\d{2}-\d{4}"
        med_record_pattern = r"MRN[:\s]+\d{6,10}"
        
        ssn_found = len(re.findall(ssn_pattern, text))
        mrn_found = len(re.findall(med_record_pattern, text))
        
        entropy = min(1.0, (ssn_found * 0.5 + mrn_found * 0.3) / max(1, len(text)))
        return entropy
    
    def decompose(self, raw_input: Any) -> tuple[str, Any]:
        text = str(raw_input)
        
        # Extract sensitive data
        ssns = re.findall(r"\d{3}-\d{2}-\d{4}", text)
        mrns = re.findall(r"MRN[:\s]+(\d{6,10})", text)
        
        # Redact from structural
        structural = re.sub(r"\d{3}-\d{2}-\d{4}", "[SSN]", text)
        structural = re.sub(r"MRN[:\s]+\d{6,10}", "MRN[REDACTED]", structural)
        
        noise = {"ssns": ssns, "mrns": mrns}
        return structural, noise
    
    def is_recoverable(self, noise: Any) -> bool:
        return bool(noise.get("ssns") or noise.get("mrns"))

# Use custom analyzer
config = AuditConfig(audit_mode="semantic", rigidity_epsilon=0.0)
analyzer = MedicalRecordAnalyzer()
audit_service = IIAEService(config, analyzer)

response = "Patient SSN 123-45-6789 has appointment scheduled."
result = audit_service.process_interaction(
    audit_input=response,
    context_axioms=["Never expose patient SSN in audit logs"],
)

print(f"Entropy: {result.metadata.get('entropy_score', 'N/A')}")
```

### Example 4: Direct Kernel Access

```python
from idicoc_notary_core.audit import (
    AuditConfig,
    IIAEServiceAuditor,
    BankEntropyAnalyzer,
)

config = AuditConfig(audit_mode="mathematical", rigidity_epsilon=0.0)
analyzer = BankEntropyAnalyzer()

# Direct auditor access for advanced use
auditor = IIAEServiceAuditor(
    config,
    analyzer,
    axioms=[
        {"id": "ax1", "text": "Constraint 1"},
        {"id": "ax2", "text": "Constraint 2"},
    ],
)

# Execute audit pipeline
result = auditor.execute(
    audit_input="Response text",
    context_input=["Context 1", "Context 2"],
    context_axioms=["Axiom 1"],
    epsilon_override=0.2,
)

print(f"Canonical State: {result['canonical_state']}")
print(f"Timestamp: {result['timestamp']}")
```

---

## Module Reference

### audit/

#### IIAEService (wrapper_pipeline.py)

Main entry point. Implements `IDICOCWrapperContract`.

**Methods:**
- `initialize(config: AuditConfig) -> None`: Set up service
- `process_interaction(...) -> CanonicalStateDTO`: Single audit cycle
- `admit(audit_input: Any) -> tuple[str, dict]`: Admission phase
- `verify_compliance(canonical_state: CanonicalStateDTO, tolerance: float) -> bool`: Compliance check

#### IIAEServiceAuditor (pipeline.py)

Orchestrates the 7-stage audit kernel.

**Methods:**
- `admit(audit_input: str) -> tuple[str, dict]`: Filter via AEM
- `execute(...) -> Dict[str, Any]`: Full pipeline execution
- `verify_compliance(...)`: Validate against axioms

#### AuditConfig (config.py)

Dataclass holding all configuration parameters. See [Configuration](#configuration).

#### AxiomEngine (axioms.py)

Manages axiom injection into PropertyGraph.

**Methods:**
- `provision_graph(graph: PropertyGraph) -> None`: Add axioms to graph
- `render_axioms(graph: PropertyGraph) -> List[str]`: Extract axiom texts

#### Dissonance Strategies (strategies/)

**SemanticDissonanceStrategy**: NLI + embedding-based
- Uses `sentence-transformers` and `transformers` models
- Detects contradiction via ENTAILMENT/CONTRADICTION classification
- Computes cosine distance

**MathematicalDissonanceStrategy**: Token + frequency-based
- No neural models required
- Uses Manhattan distance on token frequencies
- Optional embedding support

Both implement abstract `DissonanceStrategy` interface.

### kernel/

#### admission/ - AnomalousEventManager (AEM)

Upstream noise filter.

**Key Classes:**
- `AnomalousEventManager`: Segregates high-entropy noise
- `EntropyAnalyzer`: Protocol for domain-specific entropy measurement

**Workflow:**
1. Decompose input into structure + noise
2. Measure entropy of noise component
3. Classify: DISCARDED_NOISE | RECOVERABLE_NOISE | ADMITTED
4. Log metrics

#### projection/ - Invariant State Generator (ISG)

Canonical projection toward invariant identity.

**Key Classes:**
- `InvariantStateGenerator`: Applies δ_fp-based collapse
- `CanonicalState`: Immutable projected state

**Workflow:**
1. Receive admitted signal
2. Apply deterministic normalization
3. Collapse to anchor if distance < δ_fp
4. Return CanonicalState with metadata

#### dse/ - Dynamic Schema Extractor (DSE)

Graph inference and schema evolution.

**Key Classes:**
- `DynamicSchemaExtractor`: Updates PropertyGraph from state

#### deviation/ - Deviation Quantifier (DQE)

Computes coalgebraic distance (disonancia).

**Key Classes:**
- `DeviationQuantifier`: Calculates D_s using λ weights

**Formula:**
```
D_s = λ_inv × d_inv + λ_logic × d_logic + λ_temporal × d_temp
```

#### manifold/ - Manifold Constructor (CMC)

Defines admissible region around invariant.

**Key Classes:**
- `ManifoldConstructor`: Builds and evolves manifold

#### custody/ - Custodial Trace Manager (CTM)

Merkle DAG + cryptographic sealing.

**Key Classes:**
- `MerkleDAG`: DAG structure with parent hashes
- `CustodialTraceManager`: Manages DAG lifecycle
- `MerkleNode`: Immutable node with hardware evidence
- `HardwareSealer`: Protocol for HMAC-based sealing
- `EnvHardwareSealer`: Uses environment key

**Workflow:**
1. Create genesis node with audit config
2. For each audit: create node with parent hash chain
3. Seal with HMAC-SHA256 (if key available)
4. Verify root hash integrity

#### graph/ - PropertyGraph

Axiom repository with conflict detection.

**Key Classes:**
- `PropertyGraph`: Directed graph of axioms

**Methods:**
- `add_axiom(id, axiom)`: Register axiom
- `detect_conflicts()`: Find opposite-polarity axioms
- `compute_axiom_density()`: Graph connectivity metric

#### source/ - SourceAnchor

Terminal coalgebra identity (constant k).

**Key Classes:**
- `SourceAnchor`: Immutable reference point

#### verification/ - Verifier

Alignment checking against axioms.

**Key Classes:**
- `InvariantVerifier`: Validates canonicalization
- `ProjectionRegistry`: Tracks projection history

#### pipeline/ - CustodialKernel

Main 7-stage engine.

**Key Classes:**
- `CustodialKernel`: Orchestrates stages 1-7

**Stages:**
1. **Admission**: Input filtering (AEM)
2. **Projection**: Canonical state (ISG)
3. **Schema**: Graph update (DSE)
4. **Manifold**: Region definition (CMC)
5. **Deviation**: Distance calculation (DQE)
6. **Correction**: Optional projection to manifold
7. **Verification**: Alignment check (Verifier)

### utils/

#### hashing.py

Cryptographic utilities.

**Functions:**
- `sha256_hex(data: str) -> str`: SHA256 hex digest
- `canonical_json(data: Any) -> str`: Deterministic JSON
- `hmac_sha256_hex(key: str, data: str) -> str`: HMAC-SHA256 signature
- `sha256_dict(data: dict) -> str`: Hash dictionary

#### logger.py

Logging infrastructure.

**Functions:**
- `get_logger(name: str)`: Get configured logger

---

## Testing

Run the test suite:

```bash
cd Idicoc_notary

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=idicoc_notary_core

# Run specific test
pytest tests/test_idicoc_wrapper.py::test_audit_config_properties
```

**Test Files:**
- `test_idicoc_wrapper.py`: Integration tests for wrapper & strategies
- `test_persistence.py`: Storage backend tests

---

## Troubleshooting

### Issue: Model Download Fails

**Symptom:** `huggingface_hub` connection error during first run

**Solution:**
```bash
# Pre-download models
python download_models.py

# Or set cache directory
export HF_HOME="/path/to/models_cache"
```

### Issue: High Memory Usage

**Symptom:** Process uses >4GB RAM with semantic strategy

**Solution:**
- Switch to mathematical strategy: `audit_mode="mathematical"`
- Reduce batch sizes in custom code
- Use lightweight embedder: `"sentence-transformers/all-MiniLM-L6-v2"` (already default)

### Issue: Compliance Verification Fails

**Symptom:** `verify_compliance()` returns False unexpectedly

**Debug:**
```python
result = audit_service.process_interaction(...)
print(f"D_s: {result.metadata['d_s']}")
print(f"Threshold: {config.rigidity_epsilon}")
print(f"Violations: {result.metadata.get('violated_axioms')}")
print(f"Hash Valid: {result.verify_integrity()}")
```

---

## Performance Characteristics

| Operation | Mode | Time | Memory |
|-----------|------|------|--------|
| Audit (single) | Semantic | ~200ms | ~400MB |
| Audit (single) | Mathematical | ~50ms | ~100MB |
| Admission (AEM) | - | ~10ms | ~20MB |
| Merkle seal (CTM) | - | ~5ms | ~10MB |
| Compliance verify | - | ~1ms | ~1MB |

**Note:** Timings are approximate and depend on input length, embedding model, and hardware.

---

## Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-audit-feature`
3. Make changes and add tests
4. Run `pytest` and ensure all tests pass
5. Commit with clear messages: `git commit -m "Add custom entropy analyzer"`
6. Push and open a Pull Request

**Code Style:**
- Black formatting: `black idicoc_notary_core/`
- Type hints required: `mypy idicoc_notary_core/`
- Follow dataclass immutability patterns

---

## License

MIT License. See [LICENSE](LICENSE) file for details.

---

## References

- **IIAE_IDICOC-DSE.pdf**: Technical specification with coalgebraic foundations
- **Audit Module README**: [Idicoc_notary/idicoc_notary_core/audit/README.md](Idicoc_notary/idicoc_notary_core/audit/README.md)
- **Python 3.10+ Documentation**: https://docs.python.org/3.10/

---

## Contact & Support

For questions or support:
- GitHub Issues: [Submit Issue]
- Email: support@iiae.io
- Documentation: [Project Wiki]

---

## Changelog

### v1.0.0 (2026-05-24)
- ✓ Initial release with semantic & mathematical strategies
- ✓ Merkle DAG custody with hardware sealing
- ✓ Full 7-stage kernel pipeline
- ✓ Notarial passivity (non-blocking audit)
- ✓ Comprehensive test suite

---

**Last Updated**: May 24, 2026  
**Status**: Stable Beta  
**Maintainers**: IIAE Contributors
