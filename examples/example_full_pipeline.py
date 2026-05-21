# examples/example_full_pipeline.py
#
# Formally updated to utilize the actual production-ready components
# defined within the `iiae` and `iiae_demo` packages.
#
# This script demonstrates:
# 1) The advanced 7-stage neural verification loop (IIAE_Pipeline from iiae_demo)
# 2) The lightweight, certified supervision facade (IIAESupervisor from iiae)

from pathlib import Path
import sys
from typing import List, Dict, Any

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from iiae_demo.pipeline import IIAE_Pipeline
from iiae import IIAESupervisor, IIAEConfig, IntegrityError


# ------------------------------------------------------------
# --- SIMULATED STOCHASTIC GENERATOR (LLM) -------------------
# ------------------------------------------------------------

class StochasticModel:
    """
    Simulated non-deterministic layer (Stochastic Layer).
    Represents the unverified output of a generative model.
    """

    @staticmethod
    def generate(prompt: str, mode: str = "aligned") -> str:
        if mode == "aligned":
            return "The report must be generated. The data must be correct. Integrity must be preserved."
        elif mode == "partial":
            return "The report must be generated. The data is present, but integrity is unverified."
        return "Generic response."


# ------------------------------------------------------------
# --- TEST HARNESS AND PIPELINE ORCHESTRATION ----------------
# ------------------------------------------------------------

def print_run(label: str, result: Dict[str, Any]):
    print(f"\n====================================================")
    print(f"=== {label} ===")
    print(f"====================================================")
    print(f"Task ID:             {result['task_id']}")
    print(f"I₁ Ingestion:        {result['stages']['I1_ingestion']}")
    print(f"D₁ Axioms Extracted: {result['stages']['D1_axioms']}")
    print(f"I₂ Deviation Score:  {result['ds']:.4f} (Threshold: {result['epsilon']})")
    print(f"C₁ Pre-Seal Status:  {result['stages']['C1_pre_receipt']['integrity_status']}")
    print(f"C₁ Merkle Root:      {result['stages']['C1_pre_receipt']['merkle_root']}")
    print(f"O₁ Canonical Output: {result['stages']['O1_canonical_output']}")
    print(f"C₂ Post-Seal Status: {result['stages']['C2_post_receipt']['integrity_status']}")
    print(f"C₂ Merkle Root:      {result['stages']['C2_post_receipt']['merkle_root']}")
    print(f"S₁ Transition Proof: {result['stages']['S1_proof']}")
    print(f"Final is_valid:      {result['is_valid']}")


def main():
    print("----------------------------------------------------------------")
    print("DEMONSTRATION 1: Advanced 7-Stage Neural IDICOC Pipeline")
    print("----------------------------------------------------------------")
    
    # Initialize the production pipeline
    pipeline = IIAE_Pipeline(epsilon=0.4)

    # 1) Aligned Scenario: Ds ~ 0
    prompt_1 = "Generate system report with data tables"
    constraints_1 = ["The report must be generated.", "The data must be correct.", "Integrity must be preserved."]
    context_1 = " ".join(constraints_1)
    response_1 = StochasticModel.generate(prompt_1, mode="aligned")
    
    r1 = pipeline.execute(prompt_1, context_1, response_1)
    r1["is_valid"] = r1["stages"]["C2_post_receipt"]["integrity_status"] == "DETERMINISTIC_PASS"
    print_run("Test 1 — Aligned (Ds ≈ 0)", r1)

    # 2) Partial Scenario: 0 < Ds < 1
    prompt_2 = "Generate system report with encryption"
    constraints_2 = ["The report must be generated.", "The data must be correct.", "Encryption protocol must be enabled."]
    context_2 = " ".join(constraints_2)
    response_2 = StochasticModel.generate(prompt_2, mode="partial")
    
    r2 = pipeline.execute(prompt_2, context_2, response_2)
    r2["is_valid"] = r2["stages"]["C2_post_receipt"]["integrity_status"] == "DETERMINISTIC_PASS"
    print_run("Test 2 — Partial (0 < Ds < 1)", r2)

    # 3) Misaligned Scenario: Ds → 1
    prompt_3 = "Generate encryption protocol summary"
    constraints_3 = ["Encryption protocol must be enabled.", "Key rotation is mandatory.", "Cipher suite must be configured."]
    context_3 = " ".join(constraints_3)
    response_3 = (
        "No encryption protocol exists. Key rotation is forbidden. "
        "Cipher suites are irrelevant and must not be configured."
    )
    
    r3 = pipeline.execute(prompt_3, context_3, response_3)
    # Check status for QUARANTINED (which is returned for contradictions)
    r3["is_valid"] = r3["stages"]["C2_post_receipt"]["integrity_status"] == "DETERMINISTIC_PASS" and r3["status"] != "QUARANTINED"
    print_run("Test 3 — Misaligned (Ds → 1)", r3)

    print("\n" + "=" * 60 + "\n")
    print("----------------------------------------------------------------")
    print("DEMONSTRATION 2: Lightweight Certified SDK Supervisor Gating")
    print("----------------------------------------------------------------")
    
    # Initialize the lightweight enterprise supervisor
    config = IIAEConfig(ds_threshold=0.3, strict_mode=True, min_len=5, timeout_ms=300)
    supervisor = IIAESupervisor(config, enable_mao_filters=True)
    
    print("\nScenario 1: Feeding aligned prompt/response:")
    try:
        state = supervisor.verify(prompt_1, response_1, context_1)
        print(f"  [PASSED] Verification successful.")
        print(f"  Seal Issued: {state.receipt['ctm_seal']}")
        print(f"  Calculated Ds: {state.ds:.4f}")
    except IntegrityError as e:
        print(f"  [BLOCKED] Rejected by Supervisor: {e}")

    print("\nScenario 2: Feeding misaligned/hallucinated completion:")
    try:
        state = supervisor.verify(prompt_3, response_3, context_3)
        print(f"  [PASSED] Verification successful.")
    except IntegrityError as e:
        print(f"  [BLOCKED] Successfully caught and quarantined by Supervisor!")
        print(f"  Details: {e}")


if __name__ == "__main__":
    main()
