import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


def _ensure_cache_dir(cache_dir: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)


def _get_auth_token(token: Optional[str] = None) -> Optional[str | bool]:
    """Retorna el token explícito, la variable de entorno o True para usar el login local."""
    if token is not None:
        return token
    env_token = os.getenv("HF_TOKEN")
    return env_token if env_token else True


# Note: Llama-specific download helpers were intentionally moved out of the core
# to avoid coupling the core library to model artifacts and heavy HF logic.


class ModelDownloader:
    """
    Descargador de alta integridad para IDICOC.

    Asegura que el espacio de estado (Embeddings), el evaluador de límites (NLI)
    y el motor estocástico (Llama) existan en memoria antes de permitir el inicio del Cold Loop.
    """

    def __init__(self, cache_dir: str = "models_cache", token: Optional[str] = None) -> None:
        self.cache_dir = cache_dir
        self.token = token or os.getenv("HF_TOKEN")
        _ensure_cache_dir(self.cache_dir)

    def download_models(
        self,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        entailment_model_name: str = "cross-encoder/nli-deberta-v3-small",
    ) -> None:
        """
        Descarga modelos base y asegura una interrupción determinista si las capas de validación no están disponibles.
        """
        from sentence_transformers import SentenceTransformer
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        auth_token = _get_auth_token(self.token)

        print(
            f"[Phase 1 - Cold Loop] Provisionando base vectorial topológica (Embeddings): {embedding_model_name}"
        )
        try:
            SentenceTransformer(
                embedding_model_name,
                cache_folder=self.cache_dir,
                token=auth_token,
            )
        except Exception as exc:
            raise SystemExit(
                f"[Phase 1 Error] Ausencia de sustrato de Embeddings. Abortando pipeline. {exc}"
            )

        print(
            f"[Phase 1 - Cold Loop] Provisionando Oráculo Semántico (NLI): {entailment_model_name}"
        )
        try:
            AutoTokenizer.from_pretrained(
                entailment_model_name,
                cache_dir=self.cache_dir,
                token=auth_token,
            )
            AutoModelForSequenceClassification.from_pretrained(
                entailment_model_name,
                cache_dir=self.cache_dir,
                token=auth_token,
            )
        except Exception as exc:
            raise SystemExit(
                f"[Phase 1 Error] Ausencia de motor Entailment. La variedad de contención no puede calcularse. Abortando. {exc}"
            )

        # Llama/artifacts provisioning if required should be handled by external
        # provider tooling (see providers/model_downloader.py) to keep the core
        # free of heavy dependencies.


if __name__ == "__main__":
    load_dotenv()

    downloader = ModelDownloader()

    print("[IIAE] Iniciando secuencia de verificación de modelos (core: embeddings + NLI)...")
    downloader.download_models()
    print(
        "[IIAE] Topología de modelos confirmada (core). For Llama artifacts use providers tooling."
    )
