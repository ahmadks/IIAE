"""
Full 7-Stage IDICOC Debug Pipeline

For auditors, researchers, and certification bodies.
NOT for production runtime — use iiae.validate() for that.

This exposes the complete pipeline:
1. AEM: Axiom Entropy Module
2. ISG: Invariant State Generator
3. DSE: Dynamic Schema Extraction
4. DQE: Deviation Quantification Engine
5. CMC: Creative Manifold Constructor
6. CTM: Custodial Traceability Module
7. Verification: Final check
"""

from typing import Dict, Any, List

from .aem import decompose_response
from .isg import canonicalize_state
from .cmc import construct_manifold_boundary, is_point_on_manifold
from iiae.dse import extract_axioms
from iiae.dqe import deviation_score, classify_ds
from iiae.ctm import create_receipt


def run_debug_pipeline(
    prompt: str,
    response: str,
    context: str,
) -> Dict[str, Any]:
    """
    Full transparent 7-stage IDICOC pipeline for auditors.

    Returns detailed state at each stage.

    Args:
        prompt: User query
        response: AI response
        context: Business rules/policy

    Returns:
        Complete pipeline trace with all 7 stages
    """

    trace = {
        "prompt": prompt,
        "response": response,
        "context": context,
        "stages": {},
    }

    # ─────────────────────────────────────────────────────────────────
    # STAGE 1: INTERCEPTION (AEM)
    # ─────────────────────────────────────────────────────────────────
    axioms = extract_axioms(context)
    structural_signal, entropy_map = decompose_response(response, axioms)

    trace["stages"]["S1_interception"] = {
        "name": "Interception / Axiom Entropy Module",
        "extracted_axioms": axioms,
        "structural_signal": structural_signal,
        "entropy_map": entropy_map,
        "axioms_count": len(axioms),
    }

    # ─────────────────────────────────────────────────────────────────
    # STAGE 2: NORMALIZATION (ISG)
    # ─────────────────────────────────────────────────────────────────
    canonical_state = canonicalize_state(prompt, response, axioms)

    trace["stages"]["S2_normalization"] = {
        "name": "Normalization / Invariant State Generator",
        "canonical_state": canonical_state,
        "state_hash": canonical_state["state_hash"],
        "deterministic": canonical_state["deterministic"],
    }

    # ─────────────────────────────────────────────────────────────────
    # STAGE 3: HASHING (DSE)
    # ─────────────────────────────────────────────────────────────────
    # In production: compute cryptographic ID
    import hashlib

    response_hash = hashlib.sha256(response.encode()).hexdigest()
    axioms_hash = hashlib.sha256("|".join(axioms).encode()).hexdigest()

    trace["stages"]["S3_hashing"] = {
        "name": "Hashing / Dynamic Schema Extraction",
        "response_hash": response_hash,
        "axioms_hash": axioms_hash,
        "merkle_ready": True,
    }

    # ─────────────────────────────────────────────────────────────────
    # STAGE 4: INDEXING (CMC)
    # ─────────────────────────────────────────────────────────────────
    manifold_boundary = construct_manifold_boundary(axioms)

    trace["stages"]["S4_indexing"] = {
        "name": "Indexing / Creative Manifold Constructor",
        "manifold_boundary_epsilon": manifold_boundary,
        "axioms_indexed": len(axioms),
    }

    # ─────────────────────────────────────────────────────────────────
    # STAGE 5: CONSENSUS (DQE)
    # ─────────────────────────────────────────────────────────────────
    ds = deviation_score(response, axioms)
    base_type = classify_ds(ds)

    within_manifold = is_point_on_manifold(
        {"response": response}, manifold_boundary, ds
    )

    trace["stages"]["S5_consensus"] = {
        "name": "Consensus / Deviation Quantification Engine",
        "ds": ds,
        "base_type": base_type,
        "manifold_boundary": manifold_boundary,
        "within_manifold": within_manifold,
        "classification": {
            "0.0": "Standard-Zero",
            "0.01-0.4": "Tolerable",
            "0.41-0.8": "Violation",
            "0.81-1.0": "Critical",
        }.get("result", base_type),
    }

    # ─────────────────────────────────────────────────────────────────
    # STAGE 6: SEALING (CTM)
    # ─────────────────────────────────────────────────────────────────
    receipt = create_receipt(
        prompt=prompt,
        response=response,
        ds=ds,
        axioms=axioms,
        model_id="debug-pipeline",
    )

    trace["stages"]["S6_sealing"] = {
        "name": "Sealing / Custodial Traceability Module",
        "ctm_seal": receipt["ctm_seal"],
        "payload": receipt["payload"],
        "cryptographic": True,
    }

    # ─────────────────────────────────────────────────────────────────
    # STAGE 7: VERIFICATION
    # ─────────────────────────────────────────────────────────────────
    from iiae.ctm import verify_receipt

    receipt_valid = verify_receipt(receipt)

    trace["stages"]["S7_verification"] = {
        "name": "Verification / Final Check",
        "receipt_valid": receipt_valid,
        "final_ds": ds,
        "safe_harbor": base_type,
        "approved": receipt_valid and within_manifold,
    }

    # ─────────────────────────────────────────────────────────────────
    # Summary
    # ─────────────────────────────────────────────────────────────────
    trace["summary"] = {
        "verified": receipt_valid and within_manifold,
        "ds": ds,
        "base_type": base_type,
        "axioms_count": len(axioms),
        "ctm_seal": receipt["ctm_seal"],
        "all_stages_complete": True,
    }

    return trace


def print_debug_trace(trace: Dict[str, Any]) -> None:
    """
    Pretty-print the debug pipeline trace for auditors.
    """

    print("\n" + "═" * 70)
    print("IIAE FULL 7-STAGE IDICOC DEBUG PIPELINE TRACE")
    print("═" * 70)

    print(f"\nPrompt: {trace['prompt'][:60]}...")
    print(f"Response: {trace['response'][:60]}...")

    print("\n" + "─" * 70)
    print("STAGES")
    print("─" * 70)

    for stage_id, stage_data in trace["stages"].items():
        print(f"\n{stage_id.upper()}: {stage_data['name']}")
        for key, value in stage_data.items():
            if key != "name":
                if isinstance(value, dict):
                    print(f"  {key}: (complex)")
                else:
                    print(f"  {key}: {value}")

    print("\n" + "─" * 70)
    print("SUMMARY")
    print("─" * 70)

    summary = trace["summary"]
    print(f"Verified: {summary['verified']}")
    print(f"Dissonance: {summary['ds']:.2%}")
    print(f"Safe Harbor: {summary['base_type']}")
    print(f"Axioms: {summary['axioms_count']}")
    print(f"CTM Seal: {summary['ctm_seal'][:30]}...")

    print("\n" + "═" * 70 + "\n")
