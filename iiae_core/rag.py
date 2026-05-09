import re
from typing import List, Dict, Any, Tuple
from .semantic import calculate_similarity

# Canonical Knowledge Base for the 5 scenarios
RAG_DOCS = [
    {
        "id": "canon_axioms",
        "text": "The system maintains the same behavior. The system does not depend on hardware or platform."
    },
    {
        "id": "scenario1_canonical",
        "text": "The system maintains the same behavior. The system does not depend on hardware or platform."
    },
    {
        "id": "scenario2_canonical",
        "text": "The system maintains the same behavior, although in rare cases it may vary depending on execution conditions."
    },
    {
        "id": "scenario3_canonical",
        "text": "The system supports a wide range of applications and can be integrated into different workflows depending on user needs."
    },
    {
        "id": "scenario4_canonical",
        "text": "The system does not maintain the same behavior and depends heavily on the hardware where it runs."
    },
    {
        "id": "scenario5_canonical",
        "text": "The system behaves consistently in all situations and operates independently of the hardware or platform where it is executed."
    },
]

class RAG_Module:
    """
    Mini-RAG Module for hallucination detection.
    Verifies if response clauses are supported by the canonical knowledge base.
    """
    def __init__(self, support_threshold: float = 0.45, strong_support_threshold: float = 0.75):
        self.support_threshold = support_threshold
        self.strong_support_threshold = strong_support_threshold

    def _split_clauses(self, text: str) -> List[str]:
        """Splits text into verifiable clauses."""
        return [p.strip() for p in re.split(r'\. |\n| and ', text) if p.strip()]

    def verify_response(self, response: str) -> Dict[str, Any]:
        """
        Analyzes the response for hallucinations by checking support in RAG_DOCS.
        """
        clauses = self._split_clauses(response)
        if not clauses:
            return {"hallucination_score": 0.0, "details": []}

        unsupported_count = 0
        details = []

        for clause in clauses:
            # Find best match in knowledge base
            max_sim = 0.0
            best_doc = ""
            
            for doc in RAG_DOCS:
                sim = calculate_similarity(clause, doc["text"])
                if sim > max_sim:
                    max_sim = sim
                    best_doc = doc["id"]
            
            status = "unsupported"
            if max_sim >= self.strong_support_threshold:
                status = "supported"
            elif max_sim >= self.support_threshold:
                status = "weakly_supported"
            else:
                unsupported_count += 1
                
            details.append({
                "clause": clause,
                "best_match": best_doc,
                "similarity": max_sim,
                "status": status
            })

        hallucination_score = unsupported_count / len(clauses)
        
        return {
            "hallucination_score": hallucination_score,
            "support_ratio": 1.0 - hallucination_score,
            "details": details
        }
