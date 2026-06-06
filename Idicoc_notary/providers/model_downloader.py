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


def _is_hf_downloading(model_name: str) -> bool:
    import sys
    if "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ:
        return False
    import subprocess
    try:
        out = subprocess.check_output(["ps", "aux"], text=True)
        for line in out.splitlines():
            if "hf download" in line and model_name in line and "grep" not in line:
                return True
    except Exception:
        pass
    return False


def _wait_for_existing_hf_download(model_name: str) -> None:
    import time
    if _is_hf_downloading(model_name):
        print(f"[Providers.ModelDownloader] Detectado un proceso existente descargando {model_name}. Esperando finalización...")
        while _is_hf_downloading(model_name):
            time.sleep(5)
        print("[Providers.ModelDownloader] El proceso existente de descarga finalizó.")


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
    
    # Wait if another process is actively downloading this model
    _wait_for_existing_hf_download(model_name)

    if is_forced:
        print("[Providers.ModelDownloader] Forzando descarga/actualización completa de Phi...")
        try:
            snapshot_download(
                repo_id=model_name,
                local_dir=local_target_dir,
                allow_patterns=allow_patterns,
                token=auth_token,
                local_files_only=False,
            )
        except Exception as e:
            print(f"[Providers.ModelDownloader] snapshot_download falló ({e}). Intentando con hf CLI...")
            import subprocess
            subprocess.run(["hf", "download", model_name, "--local-dir", str(local_target_dir)], check=True)
    else:
        try:
            # Robust verification of local cache completeness
            cache_complete = True
            if not local_target_dir.exists() or not any(local_target_dir.iterdir()):
                cache_complete = False
            else:
                index_path = local_target_dir / "model.safetensors.index.json"
                if index_path.exists():
                    try:
                        import json
                        with open(index_path, "r", encoding="utf-8") as f:
                            index_data = json.load(f)
                        weight_files = set(index_data.get("weight_map", {}).values())
                        for wf in weight_files:
                            if not (local_target_dir / wf).exists():
                                cache_complete = False
                                break
                    except Exception:
                        cache_complete = False
                else:
                    weight_files = list(local_target_dir.glob("*.safetensors")) + list(local_target_dir.glob("*.bin")) + list(local_target_dir.glob("*.gguf"))
                    if not weight_files:
                        cache_complete = False
                
                # Check for lock/incomplete files in .cache
                cache_dir_path = local_target_dir / ".cache" / "huggingface" / "download"
                if cache_dir_path.exists():
                    for f in cache_dir_path.glob("**/*"):
                        if f.suffix in (".lock", ".incomplete"):
                            cache_complete = False
                            break
            
            if not cache_complete:
                raise FileNotFoundError("Cache is incomplete or currently downloading.")

            snapshot_download(
                repo_id=model_name,
                local_dir=local_target_dir,
                allow_patterns=allow_patterns,
                token=auth_token,
                local_files_only=True,
            )
            print("[Providers.ModelDownloader] Phi ya se encuentra en caché local.")
        except Exception:
            # Check again if another process started downloading while we verified
            _wait_for_existing_hf_download(model_name)
            
            # Check cache again after waiting
            cache_complete_after_wait = True
            if not local_target_dir.exists() or not any(local_target_dir.iterdir()):
                cache_complete_after_wait = False
            else:
                index_path = local_target_dir / "model.safetensors.index.json"
                if index_path.exists():
                    try:
                        import json
                        with open(index_path, "r", encoding="utf-8") as f:
                            index_data = json.load(f)
                        weight_files = set(index_data.get("weight_map", {}).values())
                        for wf in weight_files:
                            if not (local_target_dir / wf).exists():
                                cache_complete_after_wait = False
                                break
                    except Exception:
                        cache_complete_after_wait = False
                else:
                    weight_files = list(local_target_dir.glob("*.safetensors")) + list(local_target_dir.glob("*.bin")) + list(local_target_dir.glob("*.gguf"))
                    if not weight_files:
                        cache_complete_after_wait = False
                
                cache_dir_path = local_target_dir / ".cache" / "huggingface" / "download"
                if cache_dir_path.exists():
                    for f in cache_dir_path.glob("**/*"):
                        if f.suffix in (".lock", ".incomplete"):
                            cache_complete_after_wait = False
                            break
            
            if cache_complete_after_wait:
                print("[Providers.ModelDownloader] Phi se descargó por completo en el otro proceso.")
                return

            print("[Providers.ModelDownloader] Phi no encontrada o incompleta en la caché local. Iniciando descarga...")
            try:
                snapshot_download(
                    repo_id=model_name,
                    local_dir=local_target_dir,
                    allow_patterns=allow_patterns,
                    token=auth_token,
                    local_files_only=False,
                )
            except Exception as e:
                print(f"[Providers.ModelDownloader] snapshot_download falló ({e}). Intentando con hf CLI...")
                # Re-check wait just in case
                _wait_for_existing_hf_download(model_name)
                if not (local_target_dir / "model-00001-of-00002.safetensors").exists():
                    import subprocess
                    try:
                        subprocess.run(["hf", "download", model_name, "--local-dir", str(local_target_dir)], check=True)
                    except Exception as sub_e:
                        raise RuntimeError(f"Ambos métodos de descarga (snapshot_download y hf CLI) fallaron. Error: {sub_e}")



# Alias backward compatibility
ensure_llama_downloaded = ensure_phi_downloaded
ensure_model_downloaded = ensure_phi_downloaded


class ModelDownloader:
    def __init__(self, cache_dir: str = "models_cache", token: Optional[str] = None) -> None:
        self.cache_dir = cache_dir
        self.token = token
        _ensure_cache_dir(self.cache_dir)

    def download_model(
        self,
        model_name: str = "microsoft/Phi-3.5-mini-instruct",
        force_update: bool = False,
    ) -> None:
        ensure_model_downloaded(model_name, self.cache_dir, self.token, force_update=force_update)

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


__all__ = [
    "ensure_phi_downloaded",
    "ensure_llama_downloaded",
    "ensure_model_downloaded",
    "ModelDownloader",
]
