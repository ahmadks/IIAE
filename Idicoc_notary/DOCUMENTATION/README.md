IDICOC Notary Core — Documentation

This directory contains curated documentation for the Idicoc_notary package.
It was generated automatically on 2026-06-05 by an analysis run that executed tests
and a static-dead-code scan (vulture).

Files:
- ARCHITECTURE.md — High-level architecture and component responsibilities
- MODULES.md — Per-package module summary and public API pointers
- USAGE.md — How to install, run tests, and run the demo apps
- DEAD_CODE_REPORT.md — Static analysis (vulture) output with candidates
- MAINTENANCE.md — Recommendations to remove/refactor dead code and run analysis

Guidance:
- Use `pip install -r requirements.txt` or create a virtualenv matching project requirements.
- Run tests with `python -m pytest Idicoc_notary/tests/`.
- Review DEAD_CODE_REPORT.md for candidates; confirm before deleting code.
