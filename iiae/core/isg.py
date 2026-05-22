from typing import Any


class CanonicalState:
    def __init__(self, raw_data: str, normalized: str):
        self.raw_data = raw_data
        self.data = normalized

    def __repr__(self) -> str:
        return f"CanonicalState(data={self.data!r})"


class InvariantStateGenerator:
    """Generates the canonical invariant state C (hat{V}^t)."""

    def generate(self, context: str) -> CanonicalState:
        canonical_text = " ".join(context.strip().lower().split())
        return CanonicalState(raw_data=context, normalized=canonical_text)
