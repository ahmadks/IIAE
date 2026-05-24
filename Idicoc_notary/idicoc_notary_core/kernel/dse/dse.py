from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph
from idicoc_notary_core.utils.hashing import sha256_hex


class DynamicSchemaExtractor:
    """Extracción dinámica de axiomas y construcción del Property Graph."""

    def __init__(self, property_graph: PropertyGraph):
        self.property_graph = property_graph

    def extract_axioms(self, raw_input: Any, canonical_state: Any) -> PropertyGraph:
        """Extrae axiomas del input y estado canónico, los añade al grafo."""
        axioms = self._infer_axioms(raw_input, canonical_state)
        for axiom in axioms:
            self.property_graph.add_axiom(axiom["axiom_id"], axiom)
        self.property_graph.detect_conflicts()
        return self.property_graph

    def update_graph(self, raw_input: Any, canonical_state: Any) -> PropertyGraph:
        """Actualiza el grafo con axiomas derivados de la transformación input->canonical."""
        return self.extract_axioms(raw_input, canonical_state)

    def _infer_axioms(self, raw_input: Any, canonical_state: Any) -> list[dict[str, Any]]:
        raw_text = str(raw_input) if raw_input is not None else ""
        canonical_text = str(getattr(canonical_state, "data", canonical_state))
        axioms: list[dict[str, Any]] = []

        if raw_text and canonical_text:
            subjects = self._extract_subjects(raw_text)
            objects = self._extract_subjects(canonical_text)
            predicate = "transforms_to"
            scope = "session"
            timestamp = datetime.now(timezone.utc).isoformat()

            for subject in subjects or [type(raw_input).__name__]:
                for obj in objects or [type(canonical_state).__name__]:
                    structural_repr = f"{subject}|{predicate}|{obj}|{scope}|{timestamp}"
                    signature = sha256_hex(structural_repr)
                    axiom_id = sha256_hex(signature + "||" + timestamp)
                    axioms.append(
                        {
                            "axiom_id": axiom_id,
                            "subject": subject,
                            "predicate": predicate,
                            "object": obj,
                            "scope": scope,
                            "priority": 1,
                            "polarity": "affirmative",
                            "timestamp": timestamp,
                            "structural_signature": signature,
                            "axiom_version": axiom_id,
                        }
                    )

        if not axioms:
            axioms.append(self._build_axiom_quintuple(raw_input, canonical_state))

        return axioms

    def _extract_subjects(self, text: str) -> list[str]:
        normalized = " ".join(text.lower().strip().split())
        tokens = normalized.replace(".", "").replace(",", "").split()
        if " is " in normalized:
            parts = normalized.split(" is ")
            return [parts[0].strip()]
        if " are " in normalized:
            parts = normalized.split(" are ")
            return [parts[0].strip()]
        if " has " in normalized:
            parts = normalized.split(" has ")
            return [parts[0].strip()]
        return tokens[:1]

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
        timestamp = datetime.now(timezone.utc).isoformat()
        
        structural_repr = f"{subject}|{predicate}|{obj}|{scope}|{timestamp}"
        structural_signature = sha256_hex(structural_repr)
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
