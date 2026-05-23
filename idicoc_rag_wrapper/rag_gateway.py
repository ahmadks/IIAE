from __future__ import annotations
from typing import Any, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class MiniRAGEngine:
    """Mini RAG local para recuperar contexto factual contra el estado actual."""

    def __init__(
        self,
        embedding_model_name: str = "BAAI/bge-small-en-v1.5",
        corpus: Optional[List[str]] = None,
    ) -> None:
        self.encoder = SentenceTransformer(embedding_model_name)
        self.corpus = corpus or []
        self.embeddings: Optional[np.ndarray] = None
        self._index_corpus(self.corpus)

    def _index_corpus(self, corpus: List[str]) -> None:
        self.corpus = corpus
        if corpus:
            self.embeddings = self.encoder.encode(corpus, normalize_embeddings=True)
        else:
            self.embeddings = None

    def index_corpus(self, corpus: List[str]) -> None:
        self._index_corpus(corpus)

    def retrieve(self, query: str, top_k: int = 5, min_score: float = 0.0) -> List[str]:
        if not self.corpus or self.embeddings is None:
            return []

        query_embedding = self.encoder.encode([query], normalize_embeddings=True)[0]
        similarities = cosine_similarity([query_embedding], self.embeddings)[0]
        ranked = sorted(
            zip(self.corpus, similarities),
            key=lambda item: item[1],
            reverse=True,
        )
        return [chunk for chunk, score in ranked if score >= min_score][:top_k]

    def add_documents(self, documents: List[str]) -> None:
        self.index_corpus(self.corpus + documents)
