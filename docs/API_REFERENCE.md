# IIAE SDK API Reference

## Module: `iiae` (Top-level)

### Core Functions

#### `validate(prompt, response, context, config=None, **kwargs) → dict`

High-level transaction verification combining all verification stages.

**Parameters:**
- `prompt` (str): User query or instruction
- `response` (str): AI-generated response to verify
- `context` (str): Business rules, constraints, axioms
- `config` (IIAEConfig, optional): Configuration object
- `**kwargs`: Alternative config parameters if `config` not provided

**Returns:**
```python
{
    "verified": bool,              # True if passed integrity checks
    "ds": float,                   # Dissonance coefficient (0.0-1.0)
    "base_type": str,              # "Standard-Zero", "Tolerable", "Violation", "Critical"
    "ctm_seal": str,               # Cryptographic receipt ID
    "mao": dict,                   # Forensic filter results
    "receipt": dict                # Full CTM receipt (if verified)
}
```

**Example:**
```python
from iiae import validate, IIAEConfig

result = validate(
    prompt="How do I secure a database?",
    response="Use encryption and access controls.",
    context="Security is paramount. Encryption is required.",
    ds_threshold=0.4
)

if result["verified"]:
    print(f"Response integrity: {result['base_type']}")
```

---

#### `manifest(prompt, response, context, model_id="llm-v1", state=None, extra=None) → dict`

Generates a cryptographic receipt (CTM) from verification results.

**Parameters:**
- `prompt`, `response`, `context`: Same as `validate()`
- `model_id` (str): Identifier for the model (for receipt tracking)
- `state` (EpistemicState, optional): Reuse verification state
- `extra` (dict, optional): Additional metadata

**Returns:**
```python
{
    "payload": {
        "version": "1.0.0",
        "model_id": "gpt-4",
        "timestamp": "2026-05-21T14:23:00Z",
        "ds": 0.0,
        "axioms_count": 3,
        "merkle_root": "a1b2c3d4...",
        "prompt_hash": "...",
        "response_hash": "..."
    },
    "ctm_seal": "...",
    "axioms": ["axiom1", "axiom2", ...]
}
```

**Example:**
```python
from iiae import manifest

receipt = manifest(
    prompt="Explain encryption.",
    response="Encryption protects data at rest and in transit.",
    context="Encryption is required.",
    model_id="gpt-4"
)

# Store for forensic audit
archive(receipt)
```

---

#### `audit(receipt=None, state=None) → bool`

Forensically validates a receipt against tampering.

**Parameters:**
- `receipt` (dict): Receipt from `manifest()`
- `state` (EpistemicState, optional): Receipt extracted from state

**Returns:**
- `True` if cryptographically intact
- `False` if tampered or invalid

**Example:**
```python
from iiae import audit

is_valid = audit(receipt=receipt)
if not is_valid:
    raise SecurityError("Receipt has been tampered with")
```

---

#### `build_manifest(state, extra=None) → dict`

Constructs a compact manifest for platform integration.

**Parameters:**
- `state` (EpistemicState): Verification state
- `extra` (dict, optional): Additional metadata

**Returns:**
```python
{
    "timestamp": "2026-05-21T14:23:00Z",
    "sdk_version": "1.0.0",
    "ds": 0.0,
    "base_type": "Standard-Zero",
    "axioms_count": 3,
    "ctm": {
        "seal": "...",
        "model_id": "gpt-4",
        "version": "1.0.0"
    },
    "mao": {...},
    "is_standard_zero": True,
    "extra": {...}
}
```

---

#### `build_audit_record(state, source="runtime", meta=None) → dict`

Constructs a structured audit record.

**Parameters:**
- `state` (EpistemicState): Verification state
- `source` (str): Source identifier ("runtime", "batch", etc.)
- `meta` (dict, optional): Custom metadata

**Returns:**
```python
{
    "timestamp": "2026-05-21T14:23:00Z",
    "source": "runtime",
    "ds": 0.0,
    "base_type": "Standard-Zero",
    "axioms_count": 3,
    "ctm": {...},
    "mao": {...},
    "meta": {"user_id": "12345", ...}
}
```

---

#### `log_audit_record(record, config=None) → None`

Sends a structured audit record to the configured log destination.

**Parameters:**
- `record` (dict): Audit record from `build_audit_record()`
- `config` (IIAEConfig, optional): Configuration (uses global if not provided)

**Example:**
```python
from iiae import log_audit_record, IIAEConfig

config = IIAEConfig(log_destination="file:./audit.jsonl")
log_audit_record(record, config=config)
```

---

#### `verify_audit_chain(state) → bool`

Verifies CTM integrity for an EpistemicState.

**Parameters:**
- `state` (EpistemicState): Verification state

**Returns:**
- `True` if CTM receipt is valid
- `False` otherwise

---

### Registration Functions

#### `register_mao_engine(name, engine_class)`

Registers a custom MAO (Multi-Axiom Optimizer) filter.

**Example:**
```python
from iiae import register_mao_engine
from my_engines import CustomMAOEngine

register_mao_engine("custom", CustomMAOEngine)

# Use in config
config = IIAEConfig(mao_engine_name="custom")
```

---

#### `list_registered_engines() → list`

Lists all registered MAO engines.

**Returns:**
```python
["lexical", "semantic", "custom", ...]
```

---

### Exception Classes

#### `IntegrityError`

Raised when verification fails.

```python
from iiae import IntegrityError

try:
    result = validate(...)
except IntegrityError as e:
    print(f"Integrity violation: {e}")
```

---

#### `CircuitBreakerError`

Raised when circuit breaker is open (too many failures).

```python
from iiae import CircuitBreakerError

try:
    result = validate(...)
except CircuitBreakerError as e:
    print(f"System in failure mode: {e}")
```

---

## Module: `iiae.config`

### Class: `IIAEConfig`

Configuration container for IIAE behavior.

#### Initialization

**Constructor:**
```python
IIAEConfig(
    ds_threshold=0.4,           # Safe Harbor boundary
    min_len=20,                 # Minimum axiom length
    model_id="llm-v1",          # Model identifier
    ctm_salt=None,              # Cryptographic salt
    max_trips=5,                # Max correction iterations
    timeout_ms=5000,            # Verification timeout
    audit_mode=True,            # Enable audit logging
    strict_mode=True,           # Fail-closed mode
    cb_cooldown_ms=60000,       # Circuit breaker cooldown
    log_destination="stdout",   # Logging destination
    dqe_engine_name="lexical",  # DQE implementation
    mao_engine_name="lexical",  # MAO implementation
    **kwargs
)
```

#### Properties

- `ds_threshold` (float): Safe Harbor boundary for $D_s$
- `min_len` (int): Minimum axiom length filter
- `model_id` (str): Model identifier for receipts
- `circuit_open` (bool): Circuit breaker status
- `log_destination` (str): Audit log destination

#### Environment Variables

All parameters can be set via environment:

```bash
export IIAE_DS_THRESHOLD=0.4
export IIAE_MIN_LEN=20
export IIAE_MODEL_ID=gpt-4
export IIAE_CTM_SALT=my-org-key
export IIAE_LOG_DESTINATION=file:./audit.log
export IIAE_CONFIG_PATH=/etc/iiae/config.json
```

---

## Module: `iiae.dqe`

### Function: `deviation_score(response, axioms) → float`

Computes the Dissonance Coefficient.

**Parameters:**
- `response` (str): AI response text
- `axioms` (list): Extracted axioms

**Returns:**
- float: $D_s$ value (0.0 to 1.0)

---

### Function: `classify_ds(ds) → str`

Classifies $D_s$ into a category.

**Parameters:**
- `ds` (float): Dissonance coefficient

**Returns:**
- "Standard-Zero" if $D_s = 0.0$
- "Tolerable" if $0.0 < D_s ≤ 0.4$
- "Violation" if $0.4 < D_s ≤ 0.7$
- "Critical" if $D_s > 0.7$

---

## Module: `iiae.ctm`

### Function: `create_receipt(prompt, response, ds, axioms, model_id, salt=None) → dict`

Creates a cryptographic receipt.

**Parameters:**
- `prompt` (str): Original prompt
- `response` (str): AI response
- `ds` (float): Dissonance coefficient
- `axioms` (list): Axioms used
- `model_id` (str): Model identifier
- `salt` (str, optional): Cryptographic salt

**Returns:**
```python
{
    "payload": {...},
    "ctm_seal": "...",
    "axioms": [...]
}
```

---

### Function: `verify_receipt(receipt, salt=None) → bool`

Verifies receipt integrity.

**Parameters:**
- `receipt` (dict): Receipt to verify
- `salt` (str, optional): Same salt used in creation

**Returns:**
- `True` if valid
- `False` if tampered

---

## Module: `iiae.epistemic`

### Class: `EpistemicState`

Holds verification state.

#### Constructor

```python
EpistemicState(
    ds: float,
    base_type: str,
    axioms: list,
    receipt: dict,
    mao: dict = None
)
```

#### Properties

- `ds` (float): Dissonance coefficient
- `base_type` (str): Classification ("Standard-Zero", etc.)
- `axioms` (list): Input axioms
- `receipt` (dict): CTM receipt
- `mao` (dict): Forensic filter results
- `is_standard_zero` (bool): Read-only property

---

## Module: `iiae.supervisor`

### Class: `IIAESupervisor`

Orchestrates verification pipeline.

#### Constructor

```python
IIAESupervisor(
    config: IIAEConfig = None,
    storage: IStateStorage = None,
    mao_auditor: MAOAuditor = None,
    **kwargs
)
```

#### Methods

##### `verify(prompt, response, context) → EpistemicState`

Runs full verification pipeline.

**Returns:** `EpistemicState` object

---

### Class: `IntegrityError`

Exception for verification failures.

---

### Class: `CircuitBreakerError`

Exception for system failures.

---

## Module: `iiae.mao`

### Class: `IMAOEngine`

Protocol for forensic filter implementations.

**Methods:**
- `analyze(response, axioms) → MAOReport`

---

### Function: `register_engine(name, engine_class)`

Registers a custom MAO engine.

---

### Function: `get_engine(name, **params) → IMAOEngine`

Gets a registered MAO engine.

---

### Class: `MAOAuditor`

Compares reports from multiple MAO engines.

#### Method: `compare_reports(report1, report2) → dict`

Compares two MAO reports for consistency.

---

## Common Workflows

### Workflow 1: Simple Validation

```python
from iiae import validate

result = validate(
    prompt="What is encryption?",
    response="Encryption protects data.",
    context="Encryption is important."
)

if result["verified"]:
    print(f"✅ {result['base_type']}")
else:
    print(f"❌ {result['error']}")
```

### Workflow 2: Forensic Auditing

```python
from iiae import manifest, audit

receipt = manifest(prompt, response, context)
store_in_database(receipt)

# Later, verify
is_valid = audit(receipt=receipt)
if not is_valid:
    alert_security("Receipt tampered!")
```

### Workflow 3: Enterprise Logging

```python
from iiae import validate, build_audit_record, log_audit_record

result = validate(...)
record = build_audit_record(result, source="api", meta={"user": "alice"})
log_audit_record(record)
```

---

## See Also

- **`architecture/ARCHITECTURE.md`** — System architecture
- **`architecture/MATHEMATICS.md`** — $D_s$ formal definition
- **`auditing/audit_logging.md`** — Logging configuration
