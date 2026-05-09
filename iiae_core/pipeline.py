from typing import List, Dict, Any
from .aem import AEM_Module
from .isg import ISG_Module
from .dse import DSE_Module
from .cmc import CMC_Module
from .dqe_real import DQEReal
from .primitives import sha256, canonical_json

class IIAE_Pipeline:
    """
    Unified IIAE/IDICOC-DSE Pipeline.
    Orchestrates the 6 core modules to achieve deterministic integrity.
    """
    def __init__(self, epsilon: float = 0.4):
        self.epsilon = epsilon
        self.aem = AEM_Module(entropy_threshold=0.6)
        self.isg = ISG_Module()
        self.dse = DSE_Module()
        self.cmc = CMC_Module(epsilon=epsilon)
        self.dqe = DQEReal()
        self.ctm = CTM_Module()

    def execute(self, user_query: str, context: str, ai_response: str) -> Dict[str, Any]:
        """
        Runs the full 7-stage verification loop (IDICOC Standard).
        """
        # I1: Ingestion / Signal Capture (AEM)
        y_struct, eta = self.aem.filter(context)
        ingestion_state = {"prompt": user_query, "context_filtered": y_struct}
        
        # We use the provided ai_response directly
        model_output = ai_response
        
        # Task ID generation
        task_id = sha256(user_query + canonical_json(ingestion_state))[:16]

        # Stage 2: Axiom Update (DSE)
        graph = self.dse.update(y_struct, v_hat_placeholder := self.isg.project(y_struct))
        axioms = self.dse.get_axioms_list()

        # Stage 3: Integrity (DQEReal Auditing)
        analysis = self.dqe.evaluate(axioms, model_output)
        ds_score = analysis["ds"]
        hallucination_score = analysis["hallucination_score"]
        explanations = [] # Derived from scores in UI

        # Stage 4: CTM Pre‑seal (C1)
        pre_receipt = self.ctm.seal(
            task_id=task_id,
            stage="C1_PRE_SEAL",
            input_state=ingestion_state,
            output_state={"raw_output": model_output, "axioms": axioms},
            ds=ds_score,
            epsilon=self.epsilon
        )

        # Stage 5: Output Canonicalization (O1)
        # Snap logic (placeholder for backward compatibility)
        verified_output = model_output
        canonical_output = {
            "raw": model_output,
            "verified": verified_output,
            "ds": ds_score
        }

        # Stage 6: CTM Final Seal (C2)
        post_receipt = self.ctm.seal(
            task_id=task_id,
            stage="C2_FINAL_SEAL",
            input_state=ingestion_state,
            output_state=canonical_output,
            ds=ds_score,
            epsilon=self.epsilon
        )

        # Stage 7: State‑transition proof (S1)
        proof = sha256(pre_receipt["merkle_root"] + post_receipt["merkle_root"])

        is_registered = ds_score <= self.epsilon

        return {
            "task_id": task_id,
            "status": "REGISTERED" if is_registered else "QUARANTINED",
            "is_registered": is_registered,
            "is_valid": is_registered,
            "ds": ds_score,
            "analysis": analysis,
            "epsilon": self.epsilon,
            "stages": {
                "I1_ingestion": ingestion_state,
                "D1_axioms": axioms,
                "I2_ds": ds_score,
                "C1_pre_receipt": pre_receipt,
                "O1_canonical_output": canonical_output,
                "C2_post_receipt": post_receipt,
                "S1_proof": proof
            },
            "explanations": explanations
        }
