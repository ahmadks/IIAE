# Mathematical Foundation: The Dissonance Coefficient

## Overview

The **Dissonance Coefficient ($D_s$)** is the core mathematical primitive of IIAE. It quantifies structural deviation between an AI response and the integrity boundaries defined by user axioms.

---

## Formal Definition

### State Space

The system operates over a state space $S$ composed of seven substates (one per IDICOC pipeline stage):

$$S = X_1 \times X_2 \times \cdots \times X_7$$

where $X_i$ represents the state after stage $i$.

### Dissonance Coefficient

For a candidate state $s_t$ and canonical reference $s_0$:

$$D_s(s_t, s_0) = \sup_{i \in \{1..7\}} (w_i \cdot d_i(x_i^t, x_i^0))$$

where:
- $w_i$ ∈ [0, 1]: Stage importance weight
- $d_i$: Stage-specific distance metric
- $x_i^t$, $x_i^0$: Current and reference state at stage $i$

---

## Stage-Specific Metrics

| Stage | Name | Metric | Definition | Current |
|-------|------|--------|-----------|---------|
| 1 | **Interception** | Edit Distance | Levenshtein distance | ✅ Implicit |
| 2 | **Normalization** | Euclidean | $L^2$ norm of vectors | ✅ Implicit |
| 3 | **Hashing** | Hamming | Bit-level disagreement | ✅ Implicit (SHA-256) |
| 4 | **Indexing** | Manhattan | $L^1$ path distance | ❌ Not explicit |
| 5 | **Consensus** | Discrete | Boolean match (0/1) | ✅ Implicit |
| 6 | **Sealing** | Euclidean | Embedding distance | ✅ Implicit (CTM) |
| 7 | **Verification** | Discrete | Final identity check | ✅ Implicit |

---

## Current Implementation

### Simplified Heuristic

The v1.0 implementation uses a single global heuristic instead of formal stage metrics:

$$D_s = (1 - P) + C$$

where:
- $P$ = word-overlap preservation ratio (0 to 1)
- $C$ = contradiction penalty (0 or 1)

```python
def deviation_score(response: str, axioms: list) -> float:
    preservation = (matched_axioms) / (total_axioms)
    contradiction = 1.0 if negation_detected else 0.0
    return (1.0 - preservation) + contradiction
```

### Classification

```
D_s = 0.0           →  Standard-Zero (perfect match)
0.0 < D_s ≤ 0.4    →  Tolerable (limited drift)
0.4 < D_s ≤ 0.7    →  Violation (significant drift)
D_s > 0.7          →  Critical (structural failure)
```

---

## Formal Properties (Handbook)

### Safe Harbor Condition

For a system to achieve **Limited Safe Harbor**, the following must hold:

$$D_s(s_t, s_0) \leq \frac{1}{1-L} D_s(s_1, s_0) < \tau$$

where:
- $L$ < 1: Lipschitz constant of contraction operator
- $\tau$: Invariance threshold (0.4 in current implementation)
- The bound ensures geometric decay of drift

### Theorem: Drift Decay

**Theorem 3.1 (from handbook):**  
If contraction operator $T$ has Lipschitz constant $L < 1$, then structural drift converges geometrically:

$$D_s(s_t, s_0) \leq \sum_{k=0}^{t-1} L^k \cdot D_s(s_1, s_0) = \frac{D_s(s_1, s_0)}{1-L}$$

**Status:** ⚠️ Not formally verified in current implementation

---

## Kantorovich Lifting

For distributional drift (multiple inference paths), the formal definition uses optimal transport:

$$W_p(s_t, s_0) = \left( \inf_{\gamma} \int_S \int_S D_s(x, y)^p \, d\gamma(x, y) \right)^{1/p}$$

**Status:** ❌ Not implemented in v1.0

---

## Proof of Determinism

### Hypothesis

If $D_s = 0$ (Standard-Zero), then:
1. Identical inputs → bit-identical outputs
2. No race conditions or quantization drift
3. Reproducible across heterogeneous hardware

### Current Guarantee

✅ Partial: CTM receipts are deterministic (same input → same hash)  
❌ Full: No hardware-anchored verification (HSM/TEE/ePUF required)

---

## Contraction Operator ($T$)

### Formal Definition

The operator $T: S \to \mathcal{M}$ performs a structural "snap-to-grid":

$$T(s) = \arg\min_{s' \in \mathcal{M}} D_s(s, s')$$

where $\mathcal{M}$ is the **Invariance Manifold** (valid states).

### Expected Behavior

1. If $D_s \leq \epsilon$: Apply $T$ iteratively (max 5 times)
2. If $T^k(s) \to$ manifold: Accept corrected state
3. If convergence fails: Reject as structurally inconsistent

### Current Status

❌ **Not implemented**: System rejects non-conforming outputs rather than correcting them

---

## Entropy Purge Rate (EPR)

### Definition

The EPR measures the system's ability to reject stochastic noise while preserving structure:

$$EPR = 1 - \frac{H(S_{\text{structural}})}{H(S_{\text{total}})}$$

where $H$ is Shannon entropy.

### Goal

Structural entropy should be bounded; semantic entropy can grow freely.

### Status

❌ **Not implemented**: No explicit entropy segregation (AEM missing)

---

## Comparison: Formal vs. Current

### Gap Analysis

| Aspect | Handbook | Current v1.0 | Impact |
|--------|----------|--------------|--------|
| **Stage metrics** | 7 distinct functions | 1 global heuristic | ⚠️ Reduced rigor |
| **Kantorovich lift** | Full distributional drift | Single-point comparison | ⚠️ No multi-path analysis |
| **Contraction operator** | Iterative correction | Simple rejection | ⚠️ May over-reject |
| **Lipschitz bounds** | Formally verified | Not checked | 🔴 Cannot prove drift decay |
| **EPR/AEM** | Entropy segregation | Not implemented | 🔴 Noise not isolated |
| **Hardware HSM** | Full Safe Harbor | Not integrated | 🔴 No zero-drift guarantee |

---

## Roadmap to Full Compliance

### v1.1: Metric Refinement
- Implement IDICOCState with explicit stage tracking
- Add stage-specific distance functions
- Verify Lipschitz bound empirically

### v2.0: Formal Operators
- Implement Manifold Constructor (CMC)
- Add contraction operator $T$ with convergence check
- Integrate Entropy Purge Rate measurement

### v3.0: Hardware Integration
- Add HSM/TEE support for Full Safe Harbor
- Implement attestation pipeline
- Enable deterministic replay verification

---

## See Also

- **Handbook §III:** Full mathematical development
- **`../analysis/COHERENCE_ANALYSIS.md`:** Detailed gap assessment
- **`../architecture/ARCHITECTURE.md`:** Implementation overview
