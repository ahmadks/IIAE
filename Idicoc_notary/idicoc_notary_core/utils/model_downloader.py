import os
from typing import Optional


def _ensure_cache_dir(cache_dir: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)


def _get_auth_token(token: Optional[str] = None) -> Optional[str | bool]:
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
            use_auth_token=auth_token,
        )
        AutoModelForCausalLM.from_pretrained(
            model_name,
            cache_dir=cache_dir,
            use_auth_token=auth_token,
            device_map="auto" if _is_torch_available() else None,
        )
    except Exception as exc:
        raise RuntimeError(
            f"No se pudo descargar Llama '{model_name}'. "
            f"Asegúrate de tener acceso al repositorio, haber iniciado sesión en Hugging Face "
            f"(huggingface-cli login) o de definir HF_TOKEN. Error original: {exc}"
        ) from exc

    print(f"[ModelDownloader] Llama descargado en {cache_dir}.")


def _is_torch_available() -> bool:
    """Verifica si torch está disponible para device_map."""
    try:
        import torch

        return True
    except ImportError:
        return False
