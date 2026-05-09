import os
from sentence_transformers import SentenceTransformer, util

class MiniRAG:
    def __init__(self, rag_folder="rag_docs", model_name="sentence-transformers/all-MiniLM-L6-v2"):
        # Lightweight model for Streamlit Cloud
        self.cache_dir = os.path.join(os.getcwd(), "models_cache")
        self.model = SentenceTransformer(model_name, cache_folder=self.cache_dir)
        self.docs = []
        self.embeddings = []

        if not os.path.exists(rag_folder):
            os.makedirs(rag_folder)

        for fname in os.listdir(rag_folder):
            if fname.endswith(".txt"):
                path = os.path.join(rag_folder, fname)
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read().strip()
                    self.docs.append({"id": fname, "text": text})

        if self.docs:
            self.embeddings = self.model.encode([d["text"] for d in self.docs], convert_to_tensor=True)
        else:
            print(f"Warning: No documents found in {rag_folder}")

    def query(self, clause, top_k=1):
        if not self.docs:
            return {"id": "none", "text": ""}, 0.0
            
        clause_emb = self.model.encode(clause, convert_to_tensor=True)
        scores = util.cos_sim(clause_emb, self.embeddings)[0]
        top_results = scores.topk(top_k)
        idx = top_results.indices[0].item()
        score = top_results.values[0].item()
        return self.docs[idx], score
