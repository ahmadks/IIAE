from .ctm import create_receipt, verify_receipt

class StateTransitionModel:
    def __init__(self, model_id: str = "llm-v1", ctm_salt: str = None):
        self.model_id = model_id
        self.ctm_salt = ctm_salt

    def seal(self, prompt: str, response: str, ds: float, axioms: list):
        return create_receipt(prompt, response, ds, axioms, self.model_id, salt=self.ctm_salt)

    def verify(self, receipt: dict, salt: str = None) -> bool:
        # Default to instance salt if none provided during verification
        _salt = salt if salt is not None else self.ctm_salt
        return verify_receipt(receipt, salt=_salt)
