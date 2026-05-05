# This is still a prototype for demonstration purposes only.
# It encodes a 7‑stage IDICOC-style pipeline:
# I₁: Ingestion
# D₁: DSE
# I₂: Integrity (DQE)
# C₁: CTM (pre‑seal)
# O₁: Output canonicalization
# C₂: CTM (final seal)
# S₁: State‑transition proof

import hashlib
import json
import time
import uuid
from typing import List, Dict, Any


# ------------------------------------------------------------
# --- LOW‑LEVEL DETERMINISTIC PRIMITIVES ---------------------
# ------------------------------------------------------------

def canonical_json(data: Any) -> str:
    """Canonical JSON representation (sorted keys, no whitespace)."""
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def merkle_root(leaves: List[str]) -> str:
    """Deterministic Merkle tree root for CTM receipts."""
    if not leaves:
        return sha256("")

    # Sort leaves to ensure deterministic root calculation
    level = [sha256(leaf) for leaf in sorted(leaves)]

    while len(level) > 1:
        next_level = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else left
            next_level.append(sha256(left + right))
        level = next_level

    return level[0]


# ------------------------------------------------------------
# --- STANDARD‑ZERO DETERMINISTIC VERIFICATION ---------------
# ------------------------------------------------------------

class StandardZeroIntegrity:
    """
    Deterministic verification under Standard‑Zero.
    Ds is computed as a graded structural deviation:
    - Missing axioms (1.0 penalty)
    - Partial matches (0.5 penalty)
    - Full matches (0.0 penalty)
    """

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return [t.strip().lower() for t in text.split() if t.strip()]

    @staticmethod
    def calculate_ds(output: str, axioms: List[str]) -> float:
        """
        DQE Module: Computes the Dissonance Coefficient Ds.
        0.0 = perfect structural alignment
        1.0 = total structural failure
        """
        if not axioms:
            return 0.0

        out_tokens = StandardZeroIntegrity._tokenize(output)
        total_weight = len(axioms)
        deviation = 0.0

        for ax in axioms:
            ax_tokens = StandardZeroIntegrity._tokenize(ax)
            if all(tok in out_tokens for tok in ax_tokens):
                penalty = 0.0
            elif any(tok in out_tokens for tok in ax_tokens):
                penalty = 0.5
            else:
                penalty = 1.0
            deviation += penalty

        return deviation / total_weight


# ------------------------------------------------------------
# --- DSE: DYNAMIC SCHEMA EXTRACTION (D₁) --------------------
# ------------------------------------------------------------

class DSE_Module:
    """DSE: Extracts and formalizes invariant axioms for each task."""

    def __init__(self):
        self._axioms: Dict[str, List[str]] = {}

    def formalize(self, task_id: str, constraints: List[str]) -> List[str]:
        axioms = [c.lower().strip() for c in constraints if c.strip()]
        self._axioms[task_id] = axioms
        return axioms


# ------------------------------------------------------------
# --- CTM: CUSTODIAL TRACE MODULE (C₁, C₂) -------------------
# ------------------------------------------------------------

class CTM_Module:
    """
    CTM: Implements IDICOC‑style immutable receipts.
    - C₁: Pre‑seal (integrity evaluation snapshot)
    - C₂: Final seal (post‑canonicalization)
    """

    def __init__(self):
        self.ledger: List[Dict[str, Any]] = []

    def _base_meta(
        self,
        task_id: str,
        stage: str,
        ds: float,
        epsilon: float,
        status: str
    ) -> Dict[str, Any]:
        return {
            "task_id": task_id,
            "stage": stage,
            "ds": ds,
            "threshold": epsilon,
            "status": status,
            "nonce": str(uuid.uuid4()),
            "timestamp": time.time(),
        }

    def seal(
        self,
        task_id: str,
        stage: str,
        input_state: Dict[str, Any],
        output_state: Dict[str, Any],
        ds: float,
        epsilon: float
    ) -> Dict[str, Any]:

        status = "DETERMINISTIC_PASS" if ds <= epsilon else "INTEGRITY_FAILURE"
        meta_block = self._base_meta(task_id, stage, ds, epsilon, status)

        input_json = canonical_json(input_state)
        output_json = canonical_json(output_state)
        meta_json = canonical_json(meta_block)

        root = merkle_root([input_json, output_json, meta_json])

        receipt = {
            "task_id": task_id,
            "stage": stage,
            "integrity_status": status,
            "ds": ds,
            "threshold": epsilon,
            "nonce": meta_block["nonce"],
            "timestamp": meta_block["timestamp"],
            "merkle_root": root,
        }

        self.ledger.append(receipt)
        return receipt


# ------------------------------------------------------------
# --- SIMULATED STOCHASTIC LAYER -----------------------------
# ------------------------------------------------------------

class StochasticModel:
    """
    Simulated non‑deterministic layer (Stochastic Layer).
    Represents the output of a supervised AI model.
    """

    @staticmethod
    def generate(prompt: str, mode: str = "aligned") -> str:
        if mode == "aligned":
            return (
                "System report generated. Includes report summary, data tables, "
                "and integrity notes."
            )
        elif mode == "partial":
            return (
                "System output generated. Contains some data but missing full report "
                "structure and encryption details."
            )
        elif mode == "misaligned":
            return "Random response unrelated to requested encryption protocol."
        return "Generic response."


# ------------------------------------------------------------
# --- IIAE PIPELINE (FULL 7‑STAGE IDICOC) --------------------
# ------------------------------------------------------------

class IIAE_Pipeline:
    """
    Full 7‑stage IDICOC‑style pipeline:

    I₁: Ingestion (prompt + constraints)
    D₁: DSE (axioms)
    I₂: Integrity (DQE / Ds)
    C₁: CTM pre‑seal (integrity snapshot)
    O₁: Output canonicalization
    C₂: CTM final seal (canonical snapshot)
    S₁: State‑transition proof (hash chain of C₁ → C₂)
    """

    def __init__(self, epsilon: float = 0.4):
        self.epsilon = epsilon
        self.dse = DSE_Module()
        self.ctm = CTM_Module()
        self.model = StochasticModel()

    # --- I₁: Ingestion ---
    def _ingest(self, prompt: str, constraints: List[str]) -> Dict[str, Any]:
        return {
            "prompt": prompt,
            "constraints": constraints,
        }

    # --- O₁: Output canonicalization ---
    def _canonical_output_block(
        self,
        prompt: str,
        constraints: List[str],
        axioms: List[str],
        model_output: str,
        ds: float
    ) -> Dict[str, Any]:
        return {
            "prompt": prompt,
            "constraints": constraints,
            "axioms": axioms,
            "model_output": model_output,
            "ds": ds,
        }

    # --- S₁: State‑transition proof ---
    def _state_transition_proof(
        self,
        pre_receipt: Dict[str, Any],
        post_receipt: Dict[str, Any]
    ) -> Dict[str, Any]:
        chain_input = canonical_json({
            "pre": pre_receipt["merkle_root"],
            "post": post_receipt["merkle_root"],
        })
        proof_hash = sha256(chain_input)
        return {
            "pre_merkle_root": pre_receipt["merkle_root"],
            "post_merkle_root": post_receipt["merkle_root"],
            "transition_proof": proof_hash,
        }

    def execute(self, prompt: str, constraints: List[str], mode: str = "aligned") -> Dict[str, Any]:
        # I₁: Ingestion
        task_id = sha256(prompt + canonical_json(constraints))[:16]
        ingestion_state = self._ingest(prompt, constraints)

        # D₁: DSE
        axioms = self.dse.formalize(task_id, constraints)

        # Stochastic model output
        model_output = self.model.generate(prompt, mode=mode)

        # I₂: Integrity (DQE)
        ds = StandardZeroIntegrity.calculate_ds(model_output, axioms)

        # C₁: CTM pre‑seal (before canonicalization)
        pre_output_state = {
            "raw_model_output": model_output,
            "axioms": axioms,
            "ds": ds,
        }
        pre_receipt = self.ctm.seal(
            task_id,
            stage="C1_PRE_SEAL",
            input_state=ingestion_state,
            output_state=pre_output_state,
            ds=ds,
            epsilon=self.epsilon,
        )

        # O₁: Output canonicalization
        canonical_output = self._canonical_output_block(
            prompt, constraints, axioms, model_output, ds
        )

        # C₂: CTM final seal (canonical snapshot)
        post_receipt = self.ctm.seal(
            task_id,
            stage="C2_FINAL_SEAL",
            input_state=ingestion_state,
            output_state=canonical_output,
            ds=ds,
            epsilon=self.epsilon,
        )

        # S₁: State‑transition proof
        transition_proof = self._state_transition_proof(pre_receipt, post_receipt)

        return {
            "task_id": task_id,
            "stages": {
                "I1_ingestion": ingestion_state,
                "D1_axioms": axioms,
                "I2_ds": ds,
                "C1_pre_receipt": pre_receipt,
                "O1_canonical_output": canonical_output,
                "C2_post_receipt": post_receipt,
                "S1_transition_proof": transition_proof,
            },
            "is_valid": ds <= self.epsilon,
        }


# ------------------------------------------------------------
# --- TEST HARNESS (SHOW ALL STAGE VALUES) -------------------
# ------------------------------------------------------------

if __name__ == "__main__":
    pipeline = IIAE_Pipeline(epsilon=0.4)

    def print_run(label: str, result: Dict[str, Any]):
        print(f"\n=== {label} ===")
        print(f"Task ID: {result['task_id']}")
        print(f"I₁ Ingestion: {result['stages']['I1_ingestion']}")
        print(f"D₁ Axioms: {result['stages']['D1_axioms']}")
        print(f"I₂ Ds: {result['stages']['I2_ds']}")
        print(f"C₁ Status: {result['stages']['C1_pre_receipt']['integrity_status']}")
        print(f"C₁ Merkle: {result['stages']['C1_pre_receipt']['merkle_root']}")
        print(f"O₁ Canonical Output: {result['stages']['O1_canonical_output']}")
        print(f"C₂ Status: {result['stages']['C2_post_receipt']['integrity_status']}")
        print(f"C₂ Merkle: {result['stages']['C2_post_receipt']['merkle_root']}")
        print(f"S₁ Transition Proof: {result['stages']['S1_transition_proof']}")
        print(f"Final is_valid: {result['is_valid']}")

    # 1) Aligned: Ds ~ 0
    r1 = pipeline.execute(
        "Generate system report with data tables",
        ["report", "data", "integrity"],
        mode="aligned",
    )
    print_run("Test 1 — Aligned (Ds ≈ 0)", r1)

    # 2) Partial: 0 < Ds < 1
    r2 = pipeline.execute(
        "Generate system report with encryption",
        ["report", "data", "encryption protocol"],
        mode="partial",
    )
    print_run("Test 2 — Partial (0 < Ds < 1)", r2)

    # 3) Misaligned: Ds → 1
    r3 = pipeline.execute(
        "Generate encryption protocol summary",
        ["encryption protocol", "key rotation", "cipher suite"],
        mode="misaligned",
    )
    print_run("Test 3 — Misaligned (Ds → 1)", r3)
