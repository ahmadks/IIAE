from __future__ import annotations
from datetime import datetime
from typing import Any

from idicoc_core.core.graph.property_graph import PropertyGraph
from idicoc_core.util.hashing import sha256_hex


class DynamicSchemaExtractor:
    """Extracción dinámica de axiomas y construcción del Property Graph."""

    def __init__(self, property_graph: PropertyGraph):
        self.property_graph = property_graph

    def extract_axioms(self, raw_input: Any, canonical_state: Any) -> PropertyGraph:
        """Extrae axiomas del input y estado canónico, los añade al grafo."""
        axiom_quintuple = self._build_axiom_quintuple(raw_input, canonical_state)
        self.property_graph.add_axiom(axiom_quintuple["axiom_id"], axiom_quintuple)
        self.property_graph.detect_conflicts()
        return self.property_graph

    def update_graph(self, raw_input: Any, canonical_state: Any) -> PropertyGraph:
        """Actualiza el grafo con axiomas derivados de la transformación input->canonical."""
        return self.extract_axioms(raw_input, canonical_state)

    def _build_axiom_quintuple(self, raw_input: Any, canonical_state: Any) -> dict[str, Any]:
        """
        Construye una quíntupla de axioma (S, P, O, Θ, σ) según Sección 5.2.
        S: Subject (tipo de input)
        P: Predicate (relación)
        O: Object (tipo de estado canónico)
        Θ: Scope temporal
        σ: Structural Signature (hash)
        """
        subject = type(raw_input).__name__
        predicate = "transforms_to"
        obj = type(canonical_state.data).__name__ if hasattr(canonical_state, 'data') else repr(canonical_state)
        scope = "session"
        timestamp = datetime.utcnow().isoformat()
        
        # Firma estructural: hash del axioma normalizado
        structural_repr = f"{subject}|{predicate}|{obj}|{scope}|{timestamp}"
        structural_signature = sha256_hex(structural_repr)
        
        # Versión criptográfica: v(α) = H(σ ∥ t)
        axiom_version = sha256_hex(structural_signature + "||" + timestamp)
        
        return {
            "axiom_id": axiom_version,
            "subject": subject,
            "predicate": predicate,
            "object": obj,
            "scope": scope,
            "priority": 1,
            "polarity": "affirmative",
            "timestamp": timestamp,
            "structural_signature": structural_signature,
            "axiom_version": axiom_version,
        }
