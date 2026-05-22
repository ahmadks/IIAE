from .ctm import create_receipt, verify_receipt

class StateTransitionModel:
    def __init__(self, model_id: str = "llm-v1", ctm_salt: str = None):
        self.model_id = model_id
        self.ctm_salt = ctm_salt

    def seal(
        self,
        prompt: str,
        original_response: str,
        ds: float,
        axioms: list,
        canonical_state: "CanonicalState" = None,
        corrected_response: str = None,
        epsilon: float = None,
        lambda_weights: list | None = None,
    ):
        return create_receipt(
            prompt,
            original_response,
            ds,
            axioms,
            self.model_id,
            salt=self.ctm_salt,
            canonical_data=canonical_state.data if canonical_state is not None else None,
            y_star=corrected_response,
            epsilon=epsilon,
            lambda_weights=lambda_weights,
        )

    def verify(self, receipt: dict, salt: str = None) -> bool:
        # Default to instance salt if none provided during verification
        _salt = salt if salt is not None else self.ctm_salt
        return verify_receipt(receipt, salt=_salt)
