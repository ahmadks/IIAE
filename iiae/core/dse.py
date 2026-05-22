import re
from typing import List


class PropertyGraph:
    def __init__(self, axioms: List[str], source_text: str):
        self.axioms = axioms
        self.source_text = source_text

    def __repr__(self) -> str:
        return f"PropertyGraph(axioms={len(self.axioms)}, source_text_length={len(self.source_text)})"


class DynamicSchemaExtractor:
    """Extracts operational boundaries (axioms) into a property graph."""

    def extract(self, context: str, min_len: int = 20) -> PropertyGraph:
        if not context:
            return PropertyGraph([], context)

        raw_splits = re.split(r"[.;:\n]+", context)
        seen = set()
        axioms = []

        for line in raw_splits:
            cleaned_line = " ".join(line.strip().split())
            if cleaned_line and len(cleaned_line) >= min_len:
                lower_line = cleaned_line.lower()
                if lower_line not in seen:
                    seen.add(lower_line)
                    axioms.append(cleaned_line)

        return PropertyGraph(axioms=axioms, source_text=context)
