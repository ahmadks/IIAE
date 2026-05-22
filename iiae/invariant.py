from .core.isg import InvariantStateGenerator
from .dse import extract_axioms


class InvariantEngine(InvariantStateGenerator):
    """Legacy compatibility wrapper exposing the original invariant extraction API."""

    def __init__(self, min_len: int = 20):
        self.min_len = min_len
        super().__init__()

    def from_context(self, context: str):
        return extract_axioms(context, min_len=self.min_len)
