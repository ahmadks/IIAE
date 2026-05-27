from typing import Any, Dict
import threading
import logging
from idicoc_notary_core.utils.logger import get_logger
from idicoc_notary_core.utils.embedding_utils import compute_embedding_signature


class EmbeddingService:
    """
    Servicio Singleton para gestionar la carga y acceso a los modelos de embeddings.
    Evita cargar el mismo modelo en memoria múltiples veces.
    """
    _instance = None
    _lock = threading.Lock()
    
    _models: Dict[str, Any]
    logger: logging.Logger

    def __new__(cls) -> "EmbeddingService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EmbeddingService, cls).__new__(cls)
                cls._instance._models = {}
                cls._instance.logger = get_logger("kernel.embedding_service")
            return cls._instance

    def get_embedder(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> Any:
        """
        Devuelve el modelo de embeddings especificado.
        Si no está cargado, lo carga y lo almacena en caché.
        """
        if model_name not in self._models:
            with self._lock:
                # Doble verificación para evitar condiciones de carrera
                if model_name not in self._models:
                    self.logger.info(f"Cargando modelo de embeddings: {model_name}")
                    try:
                        from sentence_transformers import SentenceTransformer
                        model = SentenceTransformer(model_name)
                        self._models[model_name] = model
                        self.logger.info(f"Modelo {model_name} cargado exitosamente.")
                    except ImportError:
                        self.logger.error("No se pudo importar sentence_transformers.")
                        self._models[model_name] = None
                    except Exception as e:
                        self.logger.error(f"Error al cargar el modelo {model_name}: {e}")
                        self._models[model_name] = None
        
        return self._models[model_name]

    def get_signature(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2", normalize: bool = True) -> str:
        """Devuelve la firma determinista del modelo y sus parámetros."""
        return compute_embedding_signature(model_name, normalize=normalize)

    def encode(self, text: str | list[str], model_name: str = "sentence-transformers/all-MiniLM-L6-v2", normalize_embeddings: bool = True) -> Any:
        """Envoltorio para generar embeddings usando el modelo cacheados."""
        model = self.get_embedder(model_name)
        if model is None:
            raise RuntimeError(f"El modelo {model_name} no pudo cargarse.")
        return model.encode(text, normalize_embeddings=normalize_embeddings)

    def clear_cache(self) -> None:
        """Limpia todos los modelos cacheados para liberar memoria."""
        with self._lock:
            self._models.clear()
            self.logger.info("Caché de modelos de embeddings limpiada.")
