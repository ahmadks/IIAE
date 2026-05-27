import hashlib
import json
from typing import Dict, Any, Optional

_SIGNATURE_CACHE: Dict[str, str] = {}

def get_sentence_transformers_version() -> str:
    """Intenta obtener la versión de sentence-transformers si está disponible."""
    try:
        import sentence_transformers
        return getattr(sentence_transformers, "__version__", "unknown")
    except ImportError:
        return "not_installed"

def compute_embedding_signature(
    model_name: str,
    normalize: bool = True,
    additional_params: Optional[Dict[str, Any]] = None
) -> str:
    """
    Calcula una firma criptográfica (SHA-256) de la configuración del modelo de embeddings.
    Incluye el nombre del modelo, la versión de la librería, y cualquier parámetro extra
    que afecte a la salida determinista.
    """
    # Generamos una clave simple para la caché en memoria local
    cache_key_dict = {
        "m": model_name,
        "n": normalize,
        "p": additional_params or {}
    }
    # Solo para caché en este hilo/proceso, no es la firma final
    cache_key = str(cache_key_dict)
    
    if cache_key in _SIGNATURE_CACHE:
        return _SIGNATURE_CACHE[cache_key]
    
    st_version = get_sentence_transformers_version()
    
    payload = {
        "model_name": model_name,
        "normalize_embeddings": normalize,
        "sentence_transformers_version": st_version,
        "additional_params": additional_params or {}
    }
    
    # Serialización determinista (canonical json)
    payload_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    signature = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    
    _SIGNATURE_CACHE[cache_key] = signature
    return signature
