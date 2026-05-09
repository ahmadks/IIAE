import re
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
    def __init__(self):
        import os
        self.cache_dir = os.path.join(os.getcwd(), "models_cache")
        # Ensure we use the lightweight model for speed and cloud compatibility
        self.embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", cache_folder=self.cache_dir)
        self.rag = MiniRAG()
        self.entail = EntailmentModel()

    def split_clauses(self, text):
        # Professional clause splitting (Case-insensitive 'and', punctuation, newlines)
        import re
        # We use regex to split by common conjunctions and sentence delimiters
        delimiters = r'(?i)\. |\n| and | but | although | however |; '
        parts = [p.strip() for p in re.split(delimiters, text) if p.strip()]
        return parts

    def get_status(self, analysis):
        """
        Determines the Epistemic Status (REGISTERED, SPECULATIVE, QUARANTINED)
        """
        p = analysis["preservation_score"]
        h = analysis["hallucination_score"]
        n = analysis["noise_score"]
        c = analysis["contradiction_score"]
        
        if c > 0.4:
            return "QUARANTINED (CONTRADICTION)", "#ef4444"
        if p < 0.65:
            return "QUARANTINED (LOW PRESERVATION)", "#ef4444"
        if h > 0.2:
            return "SPECULATIVE (HALLUCINATION)", "#f59e0b"
        if n > 0.3:
            return "SPECULATIVE (NOISE)", "#f59e0b"
        
        return "REGISTERED", "#10b981"

    def evaluate(self, axioms, response):
        clauses = self.split_clauses(response)
        if not clauses:
            clauses = [response]

        # 1. Preservation Score (Axiom Alignment)
        # We compare each axiom against every clause and take the BEST match
        ax_emb = self.embedder.encode(axioms, convert_to_tensor=True)
        clause_embeddings = self.embedder.encode(clauses, convert_to_tensor=True)
        
        sims = []
        for i in range(len(axioms)):
            axiom_sims = util.cos_sim(ax_emb[i], clause_embeddings)[0]
            # Perfect alignment means the axiom is fully contained in at least ONE clause
            sims.append(axiom_sims.max().item())
            
        preservation = compute_preservation_score(sims)

        # 2. RAG support (Hallucination & Noise Detection)
        rag_scores = []
        rag_details = []
        for c in clauses:
            doc, score = self.rag.query(c)
            rag_scores.append(score)
            
            status = "Unsupported"
            if score >= 0.80: status = "Supported"
            elif score >= 0.50: status = "Weakly Supported"
            
            rag_details.append({
                "clause": c, 
                "match": doc["id"], 
                "score": score,
                "status": status
            })

        noise = compute_noise_score(rag_scores)
        hallucination = compute_hallucination_score(rag_scores)

        # 3. Entailment (Logical Consistency)
        entail_results = []
        for ax in axioms:
            entail_results.append(self.entail.classify(ax, response))

        contradiction = compute_contradiction_score(entail_results)

        analysis = {
            "preservation_score": preservation,
            "noise_score": noise,
            "hallucination_score": hallucination,
            "contradiction_score": contradiction,
            "rag_details": rag_details,
            "entailment": entail_results,
            "ds": 1.0 - preservation
        }
        
        status, color = self.get_status(analysis)
        analysis["status"] = status
        analysis["status_color"] = color
        
        return analysis
