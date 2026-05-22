from .core.dse import DynamicSchemaExtractor


def extract_axioms(context: str, min_len: int = 20, hard_invariants: list = None):
    """Legacy compatibility wrapper for axiom extraction."""
    extractor = DynamicSchemaExtractor()
    graph = extractor.extract(context, min_len=min_len)
    return graph.axioms
