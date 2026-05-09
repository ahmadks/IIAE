from sentence_transformers import SentenceTransformer, util
from iiae_core.rag import MiniRAG
from iiae_core.entailment import EntailmentModel
from iiae_core.scores import (
    compute_preservation_score,
    compute_noise_score,
    compute_hallucination_score,
    compute_contradiction_score
)

class DQEReal:
    """
    DQEReal Engine - The professional standard for Epistemic Auditing.
    Combines semantic alignment, RAG verification, and logical entailment.
    """
    def __init__(self):
        self.embedder = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
        self.rag = MiniRAG()
        self.entail = EntailmentModel()

    def split_clauses(self, text):
        # Improved splitting logic for complex sentences
        import re
        parts = [p.strip() for p in re.split(r' and |\. | but | although | however |\n', text) if p.strip()]
        return parts

    def evaluate(self, axioms, response):
        clauses = self.split_clauses(response)
        if not clauses:
            clauses = [response]

        # 1. Preservation Score (Axiom Alignment)
        ax_emb = self.embedder.encode(axioms, convert_to_tensor=True)
        # For preservation, we check if each axiom is represented in the BEST matching clause
        clause_embeddings = self.embedder.encode(clauses, convert_to_tensor=True)
        
        sims = []
        for i in range(len(axioms)):
            # Max similarity for this axiom across all clauses
            axiom_sims = util.cos_sim(ax_emb[i], clause_embeddings)[0]
            sims.append(axiom_sims.max().item())
            
        preservation = compute_preservation_score(sims)

        # 2. RAG support (Hallucination & Noise Detection)
        rag_scores = []
        rag_matches = []
        for c in clauses:
            doc, score = self.rag.query(c)
            rag_scores.append(score)
            rag_matches.append({"clause": c, "match": doc["id"], "score": score})

        noise = compute_noise_score(rag_scores)
        hallucination = compute_hallucination_score(rag_scores)

        # 3. Entailment (Logical Consistency)
        entail_results = []
        for ax in axioms:
            # We check the logical relationship between the axiom and the WHOLE response
            entail_results.append(self.entail.classify(ax, response))

        contradiction = compute_contradiction_score(entail_results)

        # Dissonance Score (Ds) as 1 - preservation for backward compatibility
        ds = 1.0 - preservation

        return {
            "ds": ds,
            "preservation_score": preservation,
            "noise_score": noise,
            "hallucination_score": hallucination,
            "contradiction_score": contradiction,
            "raw_similarities": sims,
            "rag_support_scores": rag_scores,
            "rag_details": rag_matches,
            "entailment": entail_results
        }
