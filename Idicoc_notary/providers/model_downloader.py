import os
from pathlib import Path
from typing import Optional


def _ensure_cache_dir(cache_dir: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)


def _get_auth_token(token: Optional[str] = None) -> Optional[str | bool]:
    if token is not None:
        return token
    env_token = os.getenv("HF_TOKEN")
    return env_token if env_token else True


def ensure_phi_downloaded(
    model_name: str = "microsoft/Phi-3.5-mini-instruct",
    cache_dir: str = "models_cache",
    token: Optional[str] = None,
    force_update: bool = False,
) -> None:
    from huggingface_hub import snapshot_download

    auth_token = _get_auth_token(token)
    _ensure_cache_dir(cache_dir)

    folder_name = model_name.split("/")[-1]
    local_target_dir = Path(cache_dir) / folder_name

    is_forced = force_update or os.getenv("IIAE_FORCE_UPDATE", "").lower() in ("true", "1", "yes")

    print(f"[Providers.ModelDownloader] Verificando Phi: {model_name}")
    allow_patterns = ["*.safetensors", "*.json", "tokenizer*"]
    if is_forced:
        print("[Providers.ModelDownloader] Forzando descarga/actualización completa de Phi...")
        snapshot_download(
            repo_id=model_name,
            local_dir=local_target_dir,
            allow_patterns=allow_patterns,
            token=auth_token,
            local_files_only=False,
        )
    else:
        try:
            snapshot_download(
                repo_id=model_name,
                local_dir=local_target_dir,
                allow_patterns=allow_patterns,
                token=auth_token,
                local_files_only=True,
            )
            print("[Providers.ModelDownloader] Phi ya se encuentra en caché local.")
        except Exception:
            print("[Providers.ModelDownloader] Phi no encontrada o incompleta en la caché local. Iniciando descarga...")
            snapshot_download(
                repo_id=model_name,
                local_dir=local_target_dir,
                allow_patterns=allow_patterns,
                token=auth_token,
                local_files_only=False,
            )


# Alias backward compatibility
ensure_llama_downloaded = ensure_phi_downloaded


class ModelDownloader:
    def __init__(self, cache_dir: str = "models_cache", token: Optional[str] = None) -> None:
        self.cache_dir = cache_dir
        self.token = token
        _ensure_cache_dir(self.cache_dir)

    def download_phi(
        self,
        phi_model_name: str = "microsoft/Phi-3.5-mini-instruct",
        force_update: bool = False,
    ) -> None:
        ensure_phi_downloaded(phi_model_name, self.cache_dir, self.token, force_update=force_update)

    # Alias backward compatibility
    def download_llama(
        self,
        llama_model_name: str = "microsoft/Phi-3.5-mini-instruct",
        force_update: bool = False,
    ) -> None:
        self.download_phi(llama_model_name, force_update=force_update)


__all__ = ["ensure_phi_downloaded", "ensure_llama_downloaded", "ModelDownloader"]
