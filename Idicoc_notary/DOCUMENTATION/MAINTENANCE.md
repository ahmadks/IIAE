Maintenance & Next Steps — Removing or Validating Dead Code

This short playbook helps you triage and safely remove or repurpose the items flagged by vulture.

1) Manual review
   - For each reported symbol, open the file and search for dynamic usages (strings, getattr, importlib).
   - Confirm tests or runtime code do not reference the symbol indirectly.

2) Add tests before deletion
   - If the symbol appears unused but is conceptually valuable (e.g. public API for consumers), add a small unit-test exercising it.
   - For internal helpers that are truly unused, add a deprecation note and mark for removal.

3) Deprecation path
   - Add a small comment and `# DEPRECATED` marker and expose a thin shim that raises a clear deprecation warning.
   - Keep deprecated code for at least one release cycle and document in changelog.

4) Automated checks
   - Add `vulture` to CI with a safe threshold; have the CI create a report artifact rather than failing the build.
   - Run `ruff` and `mypy` in CI to catch unused imports, typing regressions, and signature mismatches.

5) Removal
   - Remove code in a single focused PR per module to keep the history easy to review.
   - Run test-suite and integration scenarios (demo app) before merge.

6) Optional: Sphinx docs + API reference
   - Scaffold Sphinx (`sphinx-quickstart`) and enable `autodoc`.
   - Publish HTML docs to GitHub Pages in CI.

Quick commands
--------------
- Run vulture (local):
    pip install vulture
    vulture idicoc_notary/idicoc_notary_core --min-confidence 60

- Run ruff & mypy:
    pip install ruff mypy
    ruff check idicoc_notary
    mypy idicoc_notary

If you want, I can:
- Scaffold Sphinx documentation with autodoc and add a CI workflow to build docs.
- Create an automated `vulture` CI job that fails only on new unused code (regression) and archives the report.
