import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

def _ensure_cache_dir(cache_dir: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)

class ModelDownloader:
    def __init__(self, cache_dir: str = "models_cache", token: Optional[str] = None) -> None:
        self.cache_dir = cache_dir
        self.token = token or os.getenv("HF_TOKEN")
        _ensure_cache_dir(self.cache_dir)

    def download_models(
        self,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        entailment_model_name: str = "cross-encoder/nli-deberta-v3-small",
    ) -> None:
        from sentence_transformers import SentenceTransformer
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        print(f"Downloading embedding model: {embedding_model_name}")
        SentenceTransformer(
            embedding_model_name,
            cache_folder=self.cache_dir,
            token=self.token,
        )

        print(f"Downloading entailment model: {entailment_model_name}")
        AutoTokenizer.from_pretrained(
            entailment_model_name,
            cache_dir=self.cache_dir,
            token=self.token,
        )
        AutoModelForSequenceClassification.from_pretrained(
            entailment_model_name,
            cache_dir=self.cache_dir,
            token=self.token,
        )

if __name__ == "__main__":
    downloader = ModelDownloader()
    downloader.download_models()
