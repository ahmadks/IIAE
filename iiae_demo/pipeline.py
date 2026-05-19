from typing import List, Dict, Any
from .aem import AEM_Module
from .isg import ISG_Module
from .dse import DSE_Module
from .cmc import CMC_Module
from .dqe_real import DQEReal
from .ctm import CTM_Module
from .primitives import sha256, canonical_json

class IIAE_Pipeline:
    """
    Unified IIAE/IDICOC-DSE Pipeline with Internal Lazy-Loading.
    Optimized for Streamlit Cloud deployment.
    """
    def __init__(self, epsilon: float = 0.4):
        self.epsilon = epsilon
        self._aem = None
        self._isg = None
        self._dse = None
        self._cmc = None
        self._dqe = None
        self._ctm = None

    @property
    def aem(self):
        if self._aem is None: self._aem = AEM_Module(entropy_threshold=0.6)
        return self._aem

    @property
    def isg(self):
        if self._isg is None: self._isg = ISG_Module()
        return self._isg

    @property
    def dse(self):
        if self._dse is None: self._dse = DSE_Module()
        return self._dse

    @property
    def cmc(self):
        if self._cmc is None: self._cmc = CMC_Module(epsilon=self.epsilon)
        return self._cmc

    @property
    def dqe(self):
        if self._dqe is None: self._dqe = DQEReal()
        return self._dqe

    @property
    def ctm(self):
        if self._ctm is None: self._ctm = CTM_Module()
        return self._ctm

    def execute(self, user_query: str, context: str, ai_response: str) -> Dict[str, Any]:
        """
        Runs the full 7-stage verification loop using lazy-loaded modules.
        """
        # I1: Ingestion / Signal Capture (AEM)
        y_struct, eta = self.aem.filter(context)
        ingestion_state = {"prompt": user_query, "context_filtered": y_struct}
        model_output = ai_response
        task_id = sha256(user_query + canonical_json(ingestion_state))[:16]

        # Stage 2: Axiom Update (DSE)
        graph = self.dse.update(y_struct, self.isg.project(y_struct))
        axioms = self.dse.get_axioms_list()

        # Stage 3: Integrity (DQEReal Auditing)
        analysis = self.dqe.evaluate(axioms, model_output)
        ds_score = analysis["ds"]

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
        verified_output = model_output
        canonical_output = {"raw": model_output, "verified": verified_output, "ds": ds_score}

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
        is_registered = analysis["status"] in ["REGISTERED", "SPECULATIVE"]

        return {
            "task_id": task_id,
            "status": analysis["status"],
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
            }
        }
