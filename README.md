# IIAE / IDICOC‑DSE — Deterministic Integrity Architecture (Prototype)

[![License: BUSL-1.1](https://img.shields.io/badge/License-BUSL--1.1-blue.svg)](LICENSE)
[![Standard](https://img.shields.io/badge/Specification-Standard--Zero-black)](https://github.com/your-repo)

This repository contains a minimal prototype of the **IIAE / IDICOC‑DSE** deterministic integrity architecture. The system demonstrates how structural invariants, deviation metrics, and custodial traceability can supervise stochastic AI systems in a reproducible and auditable way.

---

## 🔧 Core Components

The architecture acts as a **Deterministic Verification Layer (DVL)**:

*   **1. Dynamic Schema Extraction (DSE):** Formalizes task‑specific axioms and structural constraints (Axiom Memory) from input/output behavior.
*   **2. Deviation Quantification Engine (DQE):** Computes the **Dissonance Coefficient ($D_s$)**, measuring structural drift and non‑invariant behavior.
*   **3. Custodial Trace Module (CTM):** Generates reproducible audit receipts using **Merkle-based proofs** for immutable verification.
*   **4. Deterministic Supervisor Layer:** Enforces invariant‑based constraints over stochastic model outputs, ensuring execution stays within the **Creative Manifold**.

---

## 📐 Architecture Overview

The prototype implements a streamlined pipeline to eliminate "hallucinations" through structural grounding:

`Input` → `DSE` → `DQE` → `Supervisor` → `CTM` → `Output + Audit Receipt`

This framework isolates non‑structural noise and enforces reproducible execution boundaries, regardless of the underlying AI model.

---

## 🚀 Example Usage

```python
from iiae.dse import extract_axioms
from iiae.dqe import compute_ds
from iiae.supervisor import enforce_invariants
from iiae.ctm import generate_receipt

# 1. Formalize structural constraints
axioms = extract_axioms(task_data)

# 2. Measure deviation of stochastic output
ds = compute_ds(model_output, axioms)

# 3. Enforce deterministic boundaries
safe_output = enforce_invariants(model_output, axioms, ds)

# 4. Generate immutable audit trail (IDICOC)
receipt = generate_receipt(safe_output, ds)

print(f"Verified Output: {safe_output}")
print(f"Audit Receipt: {receipt}")
```

---

## 📁 Repository Structure

```text
├── examples/        # Minimal usage and integration examples
├── tests/           # Test harness for integrity verification
├── README.md
└── LICENSE
```

---

## 🔒 License

This prototype is released under the **Business Source License 1.1 (BUSL‑1.1)**.
Commercial use is restricted until the Change Date specified in the `LICENSE` file.

## 📄 Notes

*   This is a prototype supporting the upcoming **PCT filing** and **Standard‑Zero specification**.
*   It is a minimal, inspectable demonstration of core deterministic integrity mechanisms and not the full enterprise implementation.

---

**Author:** Ahmad Kamal Salah  
**Location:** Glasgow, Scotland
