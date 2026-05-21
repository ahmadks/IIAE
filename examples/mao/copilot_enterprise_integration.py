#!/usr/bin/env python3
"""Copilot Enterprise–style MAO integration (Annex V).

Uses existing project utilities:
  - ``download_models.py`` — pre-cache models (optional)
  - ``iiae_demo`` — ``MiniRAG``, ``EntailmentModel`` (load on init)
  - ``ExampleSemanticMAOEngine`` — plugs into ``IMAOEngine``

    python download_models.py
    python examples/mao/copilot_enterprise_integration.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from iiae import IIAEConfig, validate
from iiae.mao.auditor import MAOAuditor
from iiae.mao.lexical import LexicalMAOEngine
from iiae.mao.registry import list_registered_engines, register_engine

PROMPT = "What is the capital of France?"
RESPONSE = "France is a country in Europe. Its capital city is Paris."
CONTEXT = RESPONSE


class CopilotSemanticMAOStub(LexicalMAOEngine):
    def geoclimatic_synchrony(self, response: str, rag_context: str) -> dict:
        report = super().geoclimatic_synchrony(response, rag_context)
        report["metadata"] = {"origin": "copilot_semantic_stub"}
        return report


def _register_stub() -> None:
    if "copilot_semantic" not in list_registered_engines():
        register_engine("copilot_semantic", CopilotSemanticMAOStub)


def run_lexical() -> None:
    print("\n--- IIAE + MAO lexical (Annex V, no ML) ---")
    cfg = IIAEConfig(enable_mao_filters=True, strict_mode=False)
    result = validate(PROMPT, RESPONSE, CONTEXT, config=cfg)
    print("Verified:", result["verified"])
    for key in (
        "material_causality",
        "probability_entropy",
        "axiomatic_invariance",
        "geoclimatic_synchrony",
    ):
        print(f"  {key}:", result["mao"].get(key))


def run_copilot_stub() -> None:
    print("\n--- IIAE + registered Copilot stub ---")
    _register_stub()
    cfg = IIAEConfig(
        enable_mao_filters=True,
        mao_engine_name="copilot_semantic",
        strict_mode=False,
    )
    result = validate(PROMPT, RESPONSE, CONTEXT, config=cfg)
    print("Verified:", result["verified"])


def run_cross_audit() -> None:
    print("\n--- MAO cross-audit (lexical vs stub) ---")
    _register_stub()
    auditor = MAOAuditor(LexicalMAOEngine(), CopilotSemanticMAOStub())
    axioms = [CONTEXT]
    print("Material:", auditor.audit_material_causality(RESPONSE, CONTEXT))
    print("Borel:", auditor.audit_probability_entropy(RESPONSE, CONTEXT, axioms))


def run_ml_semantic() -> None:
    try:
        from examples.mao.semantic_mao_engine import ExampleSemanticMAOEngine
    except ImportError:
        print("\n--- ML semantic engine skipped (pip install 'iiae[core]') ---")
        return

    if "example_semantic" not in list_registered_engines():
        register_engine("example_semantic", ExampleSemanticMAOEngine)

    print("\n--- Pre-cache via download_models.py (optional) ---")
    script = ROOT / "download_models.py"
    if script.exists():
        subprocess.run([sys.executable, str(script)], cwd=str(ROOT), check=False)

    print("--- IIAE + ExampleSemanticMAOEngine (MiniRAG + EntailmentModel) ---")
    cfg = IIAEConfig(
        enable_mao_filters=True,
        mao_engine_name="example_semantic",
        strict_mode=False,
    )
    result = validate(PROMPT, RESPONSE, CONTEXT, config=cfg)
    print("Verified:", result["verified"])
    print("MAO:", result.get("mao"))


def main() -> None:
    run_lexical()
    run_copilot_stub()
    run_cross_audit()
    run_ml_semantic()


if __name__ == "__main__":
    main()
