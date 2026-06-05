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


def ensure_llama_downloaded(
    model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct",
    cache_dir: str = "models_cache",
    token: Optional[str] = None,
) -> None:
    """
    Asegura que el modelo Llama esté disponible en caché.
    Implementa un mecanismo Fail-Safe estricto: si la descarga falla, el pipeline se aborta.
    """
    from huggingface_hub import snapshot_download

    auth_token = _get_auth_token(token)
    _ensure_cache_dir(cache_dir)

    folder_name = model_name.split("/")[-1]
    local_target_dir = Path(cache_dir) / folder_name

    print(
        f"[ModelDownloader] Verificando/Descargando Llama para compilación de políticas: {model_name}"
    )
    try:
        snapshot_download(
            repo_id=model_name,
            local_dir=local_target_dir,
            # Asegúrate de que 'original/*' incluye los safetensors/pesos que tu loader específico necesita
            allow_patterns=["original/*", "*.safetensors", "*.json", "tokenizer*"],
            token=auth_token,
        )
        print(f"[ModelDownloader] Inferencia Llama gestionada correctamente en: {local_target_dir}")
    except Exception as exc:
        # Mecanismo FAIL-SAFE: Abortar ejecución para prevenir corrupción de estado coalgebraico
        raise RuntimeError(
            f"[Fallo de Integridad Fatal] No se pudo instanciar Llama '{model_name}'. "
            f"La validación determinista no puede garantizarse. Abortando. Detalles: {exc}"
        ) from exc


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
        include_llama: bool = False,
        llama_model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct",
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

        # Ejecución controlada de Llama
        if include_llama:
            self.download_llama(llama_model_name)

    def download_llama(self, model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct") -> None:
        ensure_llama_downloaded(model_name, self.cache_dir, self.token)


if __name__ == "__main__":
    load_dotenv()

    downloader = ModelDownloader()

    include_llama = "--with-llama" in sys.argv
    llama_model = "meta-llama/Meta-Llama-3-8B-Instruct"

    for i, arg in enumerate(sys.argv):
        if arg == "--llama-model" and i + 1 < len(sys.argv):
            llama_model = sys.argv[i + 1]
            include_llama = True

    print("[IIAE] Iniciando secuencia de verificación de modelos...")
    # Si esta llamada finaliza sin lanzar excepciones, el universo F_k es seguro.
    downloader.download_models(include_llama=include_llama, llama_model_name=llama_model)
    print("[IIAE] Topología de modelos confirmada. Sistema listo para inicializar Fase 1.")
