from .ctm import create_receipt, verify_receipt

class StateTransitionModel:
    def __init__(self, model_id: str = "llm-v1"):
        self.model_id = model_id

    def seal(self, prompt: str, response: str, ds: float, axioms: list):
        return create_receipt(prompt, response, ds, axioms, self.model_id)

    def verify(self, receipt: dict) -> bool:
        return verify_receipt(receipt)
