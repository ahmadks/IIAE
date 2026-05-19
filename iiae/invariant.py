from .dse import extract_axioms

class InvariantEngine:
    def __init__(self, min_len: int = 20):
        self.min_len = min_len

    def from_context(self, context: str):
        return extract_axioms(context, min_len=self.min_len)
