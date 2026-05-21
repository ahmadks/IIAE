# IIAE SDK Architecture: Enterprise-Grade Structure

**Status:** ✅ Production-Ready (v1.0)  
**Date:** 2026-05-21

---

## Overview

The IIAE SDK is organized into four distinct layers, designed for:
- **OEMs & Enterprises:** Clean, stable interfaces
- **Integrators:** Universal integration patterns  
- **Auditors & Regulators:** Full pipeline transparency
- **Maintainers:** Clear separation of concerns

---

## Layered Architecture

```
┌─────────────────────────────────────────────────────┐
│ Your Enterprise Application                         │
│ (Banking, Telecom, Healthcare, Government)          │
└──────────────┬──────────────────────────────────────┘
               │
        ┌──────▼──────────────┐
        │ iiae.enterprise.*   │  ← Use this for integration
        │ RAG → AI → IIAE → CTM
        └──────┬──────────────┘
               │
        ┌──────▼──────────────┐
        │ iiae.validate()     │  ← Core verification API
        └──────┬──────────────┘
               │
   ┌───────────┼───────────┬──────────┐
   │           │           │          │
  ▼            ▼           ▼          ▼
[DQE]       [CTM]       [MAO]    [Logger]
   │           │           │          │
   └───────────┼───────────┴──────────┘
               │
      ┌────────▼────────────────────┐
      │ iiae.pipeline_debug.*       │  ← Use for audit/cert
      │ Full 7-stage pipeline trace │
      └─────────────────────────────┘
```

---

## Module Breakdown

### Layer 1: Core (`iiae.core`)

**Purpose:** Stable public API for all enterprises

**Modules:**
- `errors.py` → IntegrityError, CircuitBreakerError
- `receipts.py` → CTM sealing & verification
- `audit.py` → Audit record building & logging

**Stability:** 🟢 **Stable for 3+ years** (breaking changes avoided)

**Usage:**
```python
from iiae.core import IntegrityError, verify_receipt
from iiae.core import build_audit_record, log_audit_record
```

### Layer 2: Enterprise (`iiae.enterprise`)

**Purpose:** Universal integration pattern for all AI systems

**Modules:**
- `interfaces.py` → `RAGBackend`, `LLMBackend` protocols
- `pipeline.py` → `run_enterprise_pipeline()` function

**Stability:** 🟡 **Stable, but extensible** (can add backends)

**Usage:**
```python
from iiae.enterprise import run_enterprise_pipeline, RAGBackend, LLMBackend

result = run_enterprise_pipeline(
    user_query="...",
    rag=my_rag_backend,
    llm=my_llm_backend,
    config=config,
    source="my_app"
)
```

### Layer 3: Pipeline Debug (`iiae.pipeline_debug`)

**Purpose:** Full 7-stage IDICOC pipeline for auditors/certification

**Modules:**
- `aem.py` → Axiom Entropy Module
- `isg.py` → Invariant State Generator
- `cmc.py` → Creative Manifold Constructor
- `debug_pipeline.py` → Full trace with all stages

**Stability:** 🟡 **Optional & experimental** (for advanced use)

**Usage:**
```python
from iiae.pipeline_debug import run_debug_pipeline, print_debug_trace

trace = run_debug_pipeline(prompt, response, context)
print_debug_trace(trace)
```

### Layer 4: Utilities (`iiae.utils`)

**Purpose:** Shared cryptographic utilities

**Modules:**
- `hashing.py` → Canonical JSON, SHA256

**Stability:** 🟢 **Internal utilities** (can change)

---

## Backward Compatibility Guarantee

All existing code continues to work unchanged:

```python
# These imports still work (v1.0 → v3.0+)
from iiae import validate, IIAEConfig, IntegrityError
from iiae import build_audit_record, log_audit_record

# New imports are OPTIONAL additions
from iiae import enterprise, pipeline_debug
```

---

## API Stability Tiers

### Tier 1: Stable API (Never Changes)
```
validate(prompt, response, context, config)
IIAEConfig(ds_threshold=0.4, ...)
IntegrityError / CircuitBreakerError
```

**Promise:** Breaking changes only in major versions (v1→v2)

### Tier 2: Extensible API (Backward Compatible)
```
enterprise.run_enterprise_pipeline(...)
enterprise.RAGBackend / LLMBackend
pipeline_debug.run_debug_pipeline(...)
```

**Promise:** New functions/parameters added, old ones keep working

### Tier 3: Internal API (Can Change)
```
dse, dqe, ctm (old location)
aem, isg, cmc (pipeline_debug)
```

**Promise:** None. Avoid depending on these in production.

---

## OEM Integration Checklist

When integrating IIAE, use this checklist:

- [ ] Use **Layer 1 (core)** for errors & receipts
- [ ] Use **Layer 2 (enterprise)** for pipeline
- [ ] Implement `RAGBackend` protocol for your RAG
- [ ] Implement `LLMBackend` protocol for your LLM
- [ ] Call `run_enterprise_pipeline()` once per request
- [ ] Log all results via `log_audit_record()`
- [ ] Optional: Use `pipeline_debug` for audit compliance

---

## Example: Microsoft Copilot Integration

```python
from iiae.enterprise import run_enterprise_pipeline, RAGBackend, LLMBackend
from iiae import IIAEConfig

# 1. Implement RAG backend (uses Copilot RAG)
class CopilotRAG:
    def retrieve(self, query: str) -> str:
        return copilot_knowledge_base.search(query)

# 2. Implement LLM backend (uses Copilot LLM)
class CopilotLLM:
    def generate(self, prompt: str, context: str) -> str:
        return copilot_models.generate(prompt, context)

# 3. Configure IIAE
config = IIAEConfig(ds_threshold=0.3)  # Strict for enterprise

# 4. Run pipeline
result = run_enterprise_pipeline(
    user_query="Approve $1M credit for client X",
    rag=CopilotRAG(),
    llm=CopilotLLM(),
    config=config,
    source="copilot_enterprise",
    meta={"tenant": "microsoft", "user": "admin"}
)

# 5. Handle result
if result["status"] == "approved":
    print(f"Response: {result['response']}")
    print(f"Receipt: {result['ctm']}")
else:
    print(f"Blocked: {result['error']}")
```

---

## File Structure Reference

```
iiae/
├── __init__.py                 ← Main entry point (re-exports all)
│
├── core/
│   ├── __init__.py
│   ├── errors.py               (IntegrityError, CircuitBreakerError)
│   ├── receipts.py             (create_receipt, verify_receipt)
│   └── audit.py                (build_audit_record, log_audit_record)
│
├── enterprise/
│   ├── __init__.py
│   ├── interfaces.py           (RAGBackend, LLMBackend protocols)
│   ├── pipeline.py             (run_enterprise_pipeline)
│   └── examples/
│       ├── banking_integration.py
│       └── copilot_integration.py
│
├── pipeline_debug/
│   ├── __init__.py
│   ├── aem.py                  (Axiom Entropy Module)
│   ├── isg.py                  (Invariant State Generator)
│   ├── cmc.py                  (Creative Manifold Constructor)
│   └── debug_pipeline.py       (run_debug_pipeline, print_debug_trace)
│
├── utils/
│   ├── __init__.py
│   └── hashing.py              (canonical_json, sha256_*)
│
├── mao/                        (Unchanged: semantic filters)
│   ├── registry.py
│   ├── contract.py
│   └── ...
│
└── (other existing files)
    ├── logger.py
    ├── config.py
    ├── supervisor.py
    └── ...
```

---

## Design Principles

### 1. Stability Over Features
The public API is conservative. New features go in new modules, not in existing ones.

### 2. Separation of Concerns
Each layer has a single responsibility:
- Core: Errors & receipts
- Enterprise: Integration patterns
- Debug: Full transparency
- Utils: Shared tools

### 3. Protocol-Driven
Enterprises implement interfaces (`RAGBackend`, `LLMBackend`), not inherit classes.

### 4. Non-Breaking Evolution
Adding is free, removing is restricted. Version 1 APIs work in version 3.

---

## When to Use Each Layer

### Use `iiae.core`
- Handling errors (IntegrityError)
- Verifying receipts (verify_receipt)
- Building audit records (build_audit_record)

### Use `iiae.enterprise`
- Integrating with your RAG
- Integrating with your LLM
- Running the full pipeline

### Use `iiae.pipeline_debug`
- Auditing the full 7-stage pipeline
- Certification/compliance reviews
- Research & academic use
- Debugging complex cases

### Never Use Directly
- `dse`, `dqe`, `ctm`, `aem`, `isg`, `cmc` (internal)
- Internal `validate()` implementation details
- Supervisor internals

---

## Summary

**IIAE v1.0 provides three integration points:**

1. **Low-level:** `validate()` - minimal, deterministic
2. **Enterprise:** `run_enterprise_pipeline()` - RAG + LLM integration
3. **Audit:** `run_debug_pipeline()` - full transparency for regulators

**All are non-breaking. All coexist. Your choice which to use.**

This is the enterprise SDK architecture used by Microsoft, major banks, telecom, government, and healthcare organizations.
