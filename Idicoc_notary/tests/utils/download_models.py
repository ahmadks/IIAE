import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _ensure_cache_dir(cache_dir: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)


class ModelDownloader:
    """
    Descargador multi-propósito de modelos para IDICOC Standard-Zero.

    Soporta tres categorías:
    1. Embeddings (sentence-transformers): para análisis semántico
    2. NLI/Entailment: para contradicción semántica (Fase 1 - Cold Loop)
    3. Llama Causal LM: para generación determinista y compilación de políticas (Phases 1-3)
    """

    def __init__(self, cache_dir: str = "models_cache", token: Optional[str] = None) -> None:
        self.cache_dir = cache_dir
        self.token = token or os.getenv("HF_TOKEN")
        _ensure_cache_dir(self.cache_dir)

    def download_models(
        self,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        entailment_model_name: str = "cross-encoder/nli-deberta-v3-small",
        include_llama: bool = False,
        llama_model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct",
    ) -> None:
        """
        Descarga modelos de embeddings, NLI y opcionalmente Llama.

        Args:
            embedding_model_name: Modelo de embeddings (por defecto: all-MiniLM-L6-v2)
            entailment_model_name: Modelo NLI (por defecto: nli-deberta-v3-small)
            include_llama: Si True, descarga también el modelo Llama para Cold Loop
            llama_model_name: Identificador del modelo Llama (defecto: Meta-Llama-3-8B-Instruct)
        """
        from sentence_transformers import SentenceTransformer
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        auth_token = self.token if self.token is not None else True

        print(f"[Phase 1 - Cold Loop] Downloading embedding model: {embedding_model_name}")
        SentenceTransformer(
            embedding_model_name,
            cache_folder=self.cache_dir,
            use_auth_token=auth_token,
        )

        print(f"[Phase 1 - Cold Loop] Downloading entailment model: {entailment_model_name}")
        AutoTokenizer.from_pretrained(
            entailment_model_name,
            cache_dir=self.cache_dir,
            use_auth_token=auth_token,
        )
        AutoModelForSequenceClassification.from_pretrained(
            entailment_model_name,
            cache_dir=self.cache_dir,
            use_auth_token=auth_token,
        )

        if include_llama:
            self.download_llama(llama_model_name)

    def download_llama(self, model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct") -> None:
        """
        Descarga modelo Llama para uso en compilación de políticas y generación (Fases 1 y 3).

        Este descarga tanto el tokenizador como el modelo de causal LM.
        El tokenizador se usa en el InvariantSynthesizer para compilar políticas → token_ids.
        El modelo se usa en el DeterministicMUXLogitsProcessor para interception de logits.

        Args:
            model_name: Identificador del modelo Llama (defecto: Meta-Llama-3-8B-Instruct)
        """
        from transformers import AutoTokenizer, AutoModelForCausalLM

        auth_token = self.token if self.token is not None else True

        print(f"[Phase 1 - Invariant Synthesizer] Downloading Llama tokenizer: {model_name}")
        tokenizer = AutoTokenizer.from_pretrained(
            model_name,
            cache_dir=self.cache_dir,
            use_auth_token=auth_token,
        )
        print(f"[Phase 1 - Invariant Synthesizer] Tokenizer vocabulary size: {len(tokenizer)}")

        print(f"[Phase 1 - Invariant Synthesizer] Downloading Llama causal LM: {model_name}")
        AutoModelForCausalLM.from_pretrained(
            model_name,
            cache_dir=self.cache_dir,
            use_auth_token=auth_token,
            device_map="auto" if _is_torch_available() else None,
        )
        print(f"[Phase 1 - Invariant Synthesizer] Llama model weights cached successfully.")


def _is_torch_available() -> bool:
    """Verifica si torch está disponible para device_map."""
    try:
        import torch

        return True
    except ImportError:
        return False


if __name__ == "__main__":
    import sys

    downloader = ModelDownloader()

    # Descargar solo modelos base por defecto
    include_llama = "--with-llama" in sys.argv
    llama_model = "meta-llama/Meta-Llama-3-8B-Instruct"

    # Permitir especificar modelo Llama personalizado
    for i, arg in enumerate(sys.argv):
        if arg == "--llama-model" and i + 1 < len(sys.argv):
            llama_model = sys.argv[i + 1]
            include_llama = True

    print("[IIAE Standard-Zero] Iniciando descarga de modelos...")
    downloader.download_models(include_llama=include_llama, llama_model_name=llama_model)
    print("[IIAE Standard-Zero] ¡Descargas completadas!")
