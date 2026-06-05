IDICOC Notary — Architecture Overview

Overview
--------
The IDICOC Notary Core implements a 7-stage coalgebraic audit pipeline for deterministic semantic and mathematical auditing of model outputs. The core components are arranged across three layers:

- Wrapper (audit/): public API, input adaptation, configuration and CTM (Merkle custody) integration.
- Auditor / Pipeline (audit/pipeline.py): orchestrates kernel stages and strategies; produces canonical states.
- Kernel (kernel/): pure functional transformations and core algorithms (dissonance, manifold, custody, verification).

Key modules
-----------
- audit/config.py: AuditConfig and cold-loop initialisation (policy compilation, invariant synthesizer).
- audit/wrapper_pipeline.py: `IDICOCNotaryClient` — public wrapper used by demos and clients.
- audit/dse/: Dynamic Schema Extractor (Semantic policy extraction, structural & semantic dissonance strategies, logits processor).
- audit/graph/: Policy graph, loaders and invariant synthesizer used in cold loop to generate W_bank.
- kernel/: Core pipeline, custody (Merkle DAG), manifold construction, verification registry.
- utils/: EmbeddingService, hashing utilities, logging helpers.

Design principles
-----------------
- Notarial passivity: the notary measures and records; it never blocks operational flows.
- Immutability: canonical states are cryptographically sealed (Merkle DAG) and considered append-only.
- Determinism: given same inputs, pipeline yields the same canonical signature.
- Forensic traceability: extraction_mode and other metadata fields mark degraded/heuristic fallbacks.

Notes
-----
- Cold Loop vs Hot Loop: Policy compilation (W_bank) runs once at initialization (cold loop). The Hot Loop applies deterministic logits masking at inference-time in O(1).
- The repository contains a demo UI and client simulator under `Idicoc-demo-ui/` for local testing.
