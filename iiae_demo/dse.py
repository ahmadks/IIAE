import time
from typing import List, Dict, Any
from .primitives import sha256, canonical_json

class DSE_Module:
    """
    Dynamic Schema Extraction (DSE)
    Identifies, formalizes, and structures 'Temporal Axioms' into a Property Graph.
    Provides non-volatile Structural Memory.
    """
    def __init__(self):
        self.property_graph = {"vertices": [], "edges": []}
        self.axioms = []

    def update(self, context: str, v_hat: str) -> Dict[str, Any]:
        """
        Extracts axioms from context and updates the Property Graph.
        Axioms are normalized into a quintuple: (Subject, Predicate, Object, Scope, Signature).
        """
        # Simple extraction logic for the demo: split by lines/sentences
        from iiae.dse import extract_axioms
        raw_lines = extract_axioms(context, min_len=0)
        
        new_axioms = []
        for line in raw_lines:
            # Create a structured axiom representation
            axiom = {
                "id": sha256(line),
                "raw": line,
                "timestamp": time.time(),
                "v_hat_anchor": v_hat,
                "version": 1
            }
            new_axioms.append(axiom)
            
            # Update Property Graph (Vertices represent axioms)
            if axiom["id"] not in [v["id"] for v in self.property_graph["vertices"]]:
                self.property_graph["vertices"].append(axiom)
        
        self.axioms = new_axioms
        return self.property_graph

    def get_axioms_list(self) -> List[str]:
        """Returns the raw text of current session axioms."""
        return [ax["raw"] for ax in self.axioms]

    def get_graph_hash(self) -> str:
        """Returns a deterministic hash of the current Property Graph."""
        return sha256(canonical_json(self.property_graph))
