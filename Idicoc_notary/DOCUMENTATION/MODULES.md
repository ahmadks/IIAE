IDICOC Notary — Module Summary

This file lists the primary packages and files in `idicoc_core` with short descriptions and where to find the public API.

Top-level packages
------------------
- idicoc_core.audit
  - `wrapper_pipeline.py` — `IDICOCNotaryClient`: primary public client for both numeric and semantic auditing.
  - `config.py` — `AuditConfig`: central configuration object; bootstraps cold-loop compilation.
  - `dse/` — Dynamic Schema Extractor: policy extraction, structural and semantic dissonance strategies.
  - `graph/` — Policy graph (PropertyGraph), loaders (Inline/File), invariant synth.
  - `persistence/` — CTM WAL and file backend for custody persistence.

- idicoc_core.kernel
  - `pipeline/` — Kernel orchestrator implementing the 7-stage transform.
  - `custody/merkle_dag.py` — Merkle DAG custody and receipts.
  - `manifold/` — Manifold/CMC construction utilities.
  - `verification/` — Verifier registry and projection helpers.

- idicoc_core.utils
  - `embedding_service.py` — Centralized EmbeddingService used across DSE and synth.
  - `hashing.py` — SHA-256 helpers for structural signatures.
  - `logger.py` — Lightweight logger wrapper used throughout the codebase.

Tests
-----
Tests are under `Idicoc_notary/tests/` and exercise both logic and semantic pathways.

How to find functions/classes
----------------------------
- Public entrypoint: `IDICOCNotaryClient` (audit/wrapper_pipeline.py).
- To inspect policy extraction, open `audit/dse/dse.py` and `audit/graph/invariant_synthesizer.py`.

If you want a fully expanded API reference (Sphinx or MkDocs), I can scaffold `docs/` with `Sphinx` autodoc config and generate HTML docs from the codebase.
