import os
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from dotenv import load_dotenv


class ModelDownloader:
    """
    Descarga modelos desde Hugging Face solo si no existen en caché.
    Utiliza archivos de marcador para evitar descargas repetidas.
    """

    def __init__(self, cache_dir: str = "models_cache", use_env_token: bool = True):
        """
        Args:
            cache_dir: Directorio base para almacenar los modelos y marcadores.
            use_env_token: Si es True, carga el token desde la variable HF_TOKEN.
        """
        self.cache_dir = os.path.join(os.getcwd(), cache_dir)
        os.makedirs(self.cache_dir, exist_ok=True)

        self.token = None
        if use_env_token:
            load_dotenv()
            self.token = os.getenv("HF_TOKEN")

    def _is_model_cached(self, model_name: str) -> bool:
        """
        Verifica si un modelo ya fue descargado previamente mirando un archivo de marcador.
        """
        # Normalizar el nombre del modelo para usarlo como nombre de archivo
        safe_name = model_name.replace("/", "_").replace("\\", "_")
        marker_path = os.path.join(self.cache_dir, f".downloaded_{safe_name}.txt")
        return os.path.exists(marker_path)

    def _mark_model_cached(self, model_name: str) -> None:
        """Crea un archivo de marcador indicando que el modelo ya está descargado."""
        safe_name = model_name.replace("/", "_").replace("\\", "_")
        marker_path = os.path.join(self.cache_dir, f".downloaded_{safe_name}.txt")
        with open(marker_path, "w") as f:
            f.write(f"Model {model_name} downloaded on {__import__('datetime').datetime.now()}")

    def download_models(
        self,
        embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        entailment_model_name: str = "cross-encoder/nli-deberta-v3-small",
    ) -> None:
        """
        Descarga los modelos si no existen en caché.
        """
        print(f"--- Checking models in cache: {self.cache_dir} ---")

        # 1. Modelo de embeddings
        if not self._is_model_cached(embedding_model_name):
            print(f"Downloading embedding model: {embedding_model_name} ...")
            SentenceTransformer(
                embedding_model_name,
                cache_folder=self.cache_dir,
                token=self.token,
            )
            self._mark_model_cached(embedding_model_name)
            print("Embedding model downloaded and marked.")
        else:
            print(f"Embedding model '{embedding_model_name}' already cached. Skipping download.")

        # 2. Modelo de entailment (NLI)
        if not self._is_model_cached(entailment_model_name):
            print(f"Downloading entailment model: {entailment_model_name} ...")
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
            self._mark_model_cached(entailment_model_name)
            print("Entailment model downloaded and marked.")
        else:
            print(f"Entailment model '{entailment_model_name}' already cached. Skipping download.")

        print("--- Model download process finished ---")


# Ejemplo de uso (opcional)
if __name__ == "__main__":
    downloader = ModelDownloader(cache_dir="models_cache")
    downloader.download_models(
        embedding_model_name="sentence-transformers/all-MiniLM-L6-v2",
        entailment_model_name="facebook/bart-large-mnli",
    )
