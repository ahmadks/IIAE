import os
from typing import Optional

def _ensure_cache_dir(cache_dir: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)


def _get_auth_token(token: Optional[str] = None) -> Optional[str | bool]:
    if token is not None:
        return token
    env_token = os.getenv("HF_TOKEN")
    return env_token if env_token else True


def _is_torch_available() -> bool:
    """Verifica si torch está disponible para device_map."""
    try:
        import torch
        return True
    except ImportError:
        return False


def ensure_llama_downloaded(
    model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct",
    cache_dir: str = "models_cache",
    token: Optional[str] = None,
) -> None:
    """
    Asegura que el modelo Llama esté disponible en caché.

    Si el modelo no está descargado localmente, intenta descargarlo usando
    las credenciales de Hugging Face disponibles localmente o la variable HF_TOKEN.
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer

    auth_token = _get_auth_token(token)
    _ensure_cache_dir(cache_dir)

    # Validar si ya está en caché localmente.
    try:
        AutoTokenizer.from_pretrained(
            model_name,
            cache_dir=cache_dir,
            local_files_only=True,
        )
        AutoModelForCausalLM.from_pretrained(
            model_name,
            cache_dir=cache_dir,
            local_files_only=True,
        )
        return
    except Exception:
        pass

    # Descargar si no está presente.
    print(f"[ModelDownloader] Descargando Llama: {model_name}")
    try:
        AutoTokenizer.from_pretrained(
            model_name,
            cache_dir=cache_dir,
            token=auth_token,
        )
        AutoModelForCausalLM.from_pretrained(
            model_name,
            cache_dir=cache_dir,
            token=auth_token,
            device_map="auto" if _is_torch_available() else None,
        )
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo descargar Llama '{model_name}'. "
            f"Asegúrate de tener acceso al repositorio, haber iniciado sesión en Hugging Face "
            f"(huggingface-cli login) o de definir HF_TOKEN. Error original: {exc}"
        ) from exc

    print(f"[ModelDownloader] Llama descargado en {cache_dir}.")


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
        """
        from sentence_transformers import SentenceTransformer
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        auth_token = self.token if self.token is not None else True

        print(f"[Phase 1 - Cold Loop] Downloading embedding model: {embedding_model_name}")
        SentenceTransformer(
            embedding_model_name,
            cache_folder=self.cache_dir,
            token=auth_token,
        )

        print(f"[Phase 1 - Cold Loop] Downloading entailment model: {entailment_model_name}")
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

        if include_llama:
            self.download_llama(llama_model_name)

    def download_llama(self, model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct") -> None:
        """
        Descarga modelo Llama para uso en compilación de políticas y generación (Fases 1 y 3).
        """
        ensure_llama_downloaded(model_name, self.cache_dir, self.token)


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv

    load_dotenv()

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
