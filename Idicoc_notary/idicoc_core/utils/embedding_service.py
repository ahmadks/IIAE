from typing import Any, Dict
import threading
import logging
from idicoc_core.utils.logger import get_logger
from idicoc_core.utils.embedding_utils import compute_embedding_signature
from idicoc_core.config import DEFAULT_SEMANTIC_EMBEDDING_MODEL


class EmbeddingService:
    """
    Servicio Singleton para gestionar la carga y acceso a los modelos de embeddings.
    Evita cargar el mismo modelo en memoria múltiples veces.
    """

    _instance = None
    _lock = threading.Lock()
    _provider: Any = None

    _models: Dict[str, Any]
    logger: logging.Logger

    @classmethod
    def set_provider(cls, provider: Any) -> None:
        """Configura un proveedor de embeddings mockeable de forma global."""
        if cls._provider is not provider:
            cls._provider = provider
            if cls._instance is not None:
                cls._instance._models.clear()

    def __new__(cls) -> "EmbeddingService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EmbeddingService, cls).__new__(cls)
                cls._instance._models = {}
                cls._instance.logger = get_logger("kernel.embedding_service")
            return cls._instance

    def get_embedder(
        self, model_name: str = DEFAULT_SEMANTIC_EMBEDDING_MODEL
    ) -> Any:
        """
        Devuelve el modelo de embeddings especificado.
        Si no está cargado, lo carga y lo almacena en caché.
        """
        if self._provider is not None:
            return self._provider
        if model_name not in self._models:
            with self._lock:
                if model_name not in self._models:
                    self.logger.info(f"Cargando modelo de embeddings: {model_name}")
                    try:
                        from sentence_transformers import SentenceTransformer
                        import os

                        cache_dir = os.getenv("IIAE_CACHE_DIR", "models_cache")
                        force_update = os.getenv("IIAE_FORCE_UPDATE", "").lower() in (
                            "true",
                            "1",
                            "yes",
                        )

                        if force_update:
                            model = SentenceTransformer(
                                model_name,
                                cache_folder=cache_dir,
                                local_files_only=False,
                            )
                        else:
                            try:
                                model = SentenceTransformer(
                                    model_name,
                                    cache_folder=cache_dir,
                                    local_files_only=True,
                                )
                            except Exception:
                                self.logger.info(
                                    f"Modelo {model_name} no encontrado en caché local. Iniciando descarga..."
                                )
                                model = SentenceTransformer(
                                    model_name,
                                    cache_folder=cache_dir,
                                    local_files_only=False,
                                )

                        self._models[model_name] = model
                        self.logger.info(f"Modelo {model_name} cargado exitosamente.")
                    except ImportError:
                        self.logger.error("No se pudo importar sentence_transformers.")
                        self._models[model_name] = None
                    except Exception as e:
                        self.logger.error(f"Error al cargar el modelo {model_name}: {e}")
                        self._models[model_name] = None

        return self._models[model_name]

    def get_signature(
        self, model_name: str = DEFAULT_SEMANTIC_EMBEDDING_MODEL
    ) -> str:
        """Devuelve la firma determinista del modelo y sus parámetros."""
        return compute_embedding_signature(model_name)

    def encode(
        self,
        text: str | list[str],
        model_name: str = DEFAULT_SEMANTIC_EMBEDDING_MODEL,
    ) -> Any:
        """Envoltorio para generar embeddings usando el modelo cacheados."""
        if self._provider is not None:
            if hasattr(self._provider, "encode"):
                try:
                    return self._provider.encode(text, model_name=model_name)
                except TypeError:
                    return self._provider.encode(text)
        model = self.get_embedder(model_name)
        if model is None:
            raise RuntimeError(f"El modelo {model_name} no pudo cargarse.")
        return model.encode(text)

    def clear_cache(self) -> None:
        """Limpia todos los modelos cacheados para liberar memoria."""
        with self._lock:
            self._models.clear()
            self.logger.info("Caché de modelos de embeddings limpiada.")
