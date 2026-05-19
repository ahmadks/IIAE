from .pipeline import IIAE_Pipeline
from iiae.epistemic import EpistemicState

class CoreIIAEAdapter:
    def __init__(self, epsilon=0.4):
        self.pipeline = IIAE_Pipeline(epsilon=epsilon)

    def verify(self, user_query, context, ai_response):
        result = self.pipeline.execute(user_query, context, ai_response)
        analysis = result["analysis"]
        ds = result["ds"]
        from iiae.dqe import classify_ds
        base_type = classify_ds(ds)
        axioms = result["stages"].get("D1_axioms", [])
        
        c2_stage = result["stages"].get("C2_post_receipt", {})
        receipt = {
            "merkle_root": c2_stage.get("merkle_root", ""),
            "Ds": ds,
            "status": analysis.get("status", "UNKNOWN")
        }
        return EpistemicState(ds, base_type, axioms, receipt)
