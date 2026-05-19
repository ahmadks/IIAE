from .dqe import deviation_score, classify_ds

class IntegrityEvaluator:
    def __init__(self, threshold: float = 0.4):
        self.threshold = threshold

    def evaluate(self, response: str, axioms: list):
        ds = deviation_score(response, axioms)
        base_type = classify_ds(ds)
        return ds, base_type
