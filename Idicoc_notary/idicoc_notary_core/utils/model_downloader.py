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
    Asegura que el modelo Llama esté disponible en caché replicando el comando de terminal.
    Implementa tolerancia a fallos Standard-Zero si la autenticación falla.
    """
    from huggingface_hub import snapshot_download

    auth_token = _get_auth_token(token)
    _ensure_cache_dir(cache_dir)

    # Definir la ruta de destino local limpia basada en el nombre del modelo
    folder_name = model_name.split("/")[-1]
    local_target_dir = Path(cache_dir) / folder_name

    print(f"[ModelDownloader] Verificando/Descargando Llama optimizado: {model_name}")
    try:
        # Se elimina 'local_dir_use_symlinks' para limpiar la advertencia del framework
        snapshot_download(
            repo_id=model_name,
            local_dir=local_target_dir,
            allow_patterns=["original/*"],
            token=auth_token,
        )
        print(f"[ModelDownloader] Llama gestionado correctamente en: {local_target_dir}")
    except Exception as exc:
        # Caída suave (Fallback) de Standard-Zero para no bloquear el resto de las fases
        print(f"\n[Standard-Zero Fallback] AVISO: No se pudo descargar Llama '{model_name}'.")
        print(f"[Standard-Zero Fallback] Detalles del error: {exc}")
        print("[Standard-Zero Fallback] Continuando ejecución del pipeline sin el modelo Llama.\n")


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
        Descarga modelos de embeddings, NLI y opcionalmente Llama de forma segura.
        """
        from sentence_transformers import SentenceTransformer
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        auth_token = self.token if self.token is not None else True

        print(f"[Phase 1 - Cold Loop] Downloading embedding model: {embedding_model_name}")
        try:
            SentenceTransformer(
                embedding_model_name,
                cache_folder=self.cache_dir,
                token=auth_token,
            )
        except Exception as e:
            print(f"[ERROR] Error crítico descargando Embeddings: {e}")

        print(f"[Phase 1 - Cold Loop] Downloading entailment model: {entailment_model_name}")
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
        except Exception as e:
            print(f"[ERROR] Error crítico descargando NLI/Entailment: {e}")

        # Ejecución controlada de Llama
        if include_llama:
            self.download_llama(llama_model_name)

    def download_llama(self, model_name: str = "meta-llama/Meta-Llama-3-8B-Instruct") -> None:
        """
        Invoca la descarga optimizada de Llama con tolerancia a fallos.
        """
        ensure_llama_downloaded(model_name, self.cache_dir, self.token)


if __name__ == "__main__":
    # Cargar variables del entorno (.env) antes de inicializar nada
    load_dotenv()

    downloader = ModelDownloader()

    # Configuración de argumentos por defecto
    include_llama = "--with-llama" in sys.argv
    llama_model = "meta-llama/Meta-Llama-3-8B-Instruct"

    # Capturar modelo personalizado desde la terminal si se provee
    for i, arg in enumerate(sys.argv):
        if arg == "--llama-model" and i + 1 < len(sys.argv):
            llama_model = sys.argv[i + 1]
            include_llama = True

    print("[IIAE Standard-Zero] Iniciando descarga de modelos...")
    downloader.download_models(include_llama=include_llama, llama_model_name=llama_model)
    print("[IIAE Standard-Zero] ¡Descargas completadas o gestionadas mediante Fallback!")
