from typing import Any
import numpy as np

class StringUtils:
    """Utilidades para manejo de cadenas y embeddings de texto."""
    
    _embedding_model = None

    @classmethod
    def get_embedding_model(cls, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> Any:
        """Carga y devuelve el modelo de embeddings usando el servicio central."""
        from idicoc_notary_core.utils.embedding_service import EmbeddingService
        return EmbeddingService().get_embedder(model_name)

    @classmethod
    def embed_text(cls, text: str, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> np.ndarray:
        """Convierte texto a un vector usando el modelo de embeddings."""
        model = cls.get_embedding_model(model_name)
        if model is not None:
            # sentence-transformers devuelve np.ndarray (o torch tensor)
            embedding = model.encode(text, normalize_embeddings=True)
            return np.asarray(embedding, dtype=float)
        
        # Fallback pseudo-determinista si el modelo no está disponible
        # basado en la longitud y un hash simple para generar un vector de tamaño fijo
        import hashlib
        h = hashlib.sha256(text.encode('utf-8')).digest()
        # Generamos un vector de 384 dimensiones (típico de MiniLM) basado en el hash
        fallback = np.zeros(384, dtype=float)
        for i in range(min(384, len(h))):
            fallback[i] = float(h[i]) / 255.0
        
        # Normalizar
        norm = np.linalg.norm(fallback)
        if norm > 0:
            fallback = fallback / norm
            
        return fallback

    @classmethod
    def to_vector(cls, y: Any, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> np.ndarray:
        """Convierte cualquier entrada a un vector numérico (ndarray)."""
        if isinstance(y, str):
            return cls.embed_text(y, model_name)
        
        # Si ya es un array o lista, devolverlo como ndarray
        try:
            arr = np.asarray(getattr(y, "distribution", getattr(y, "measure_vector", y)), dtype=float)
            if arr.ndim == 1 and arr.size > 0:
                return arr
        except Exception:
            pass
            
        # Fallback final
        return cls.embed_text(str(y), model_name)
