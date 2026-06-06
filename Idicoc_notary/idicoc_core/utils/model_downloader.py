import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from idicoc_core.config import DEFAULT_SEMANTIC_EMBEDDING_MODEL, DEFAULT_SEMANTIC_NLI_MODEL


def _ensure_cache_dir(cache_dir: str) -> None:
    os.makedirs(cache_dir, exist_ok=True)


def _get_auth_token(token: Optional[str] = None) -> Optional[str | bool]:
    if token is not None:
        return token
    env_token = os.getenv("HF_TOKEN")
    return env_token if env_token else True


class ModelDownloader:
    def __init__(self, cache_dir: str = "models_cache", token: Optional[str] = None) -> None:
        self.cache_dir = cache_dir
        self.token = token or os.getenv("HF_TOKEN")
        _ensure_cache_dir(self.cache_dir)

    def download_models(
        self,
        embedding_model_name: str = DEFAULT_SEMANTIC_EMBEDDING_MODEL,
        entailment_model_name: str = DEFAULT_SEMANTIC_NLI_MODEL,
        force_update: bool = False,
    ) -> None:
        from sentence_transformers import SentenceTransformer
        from transformers import AutoTokenizer, AutoModelForSequenceClassification

        auth_token = _get_auth_token(self.token)
        is_forced = force_update or os.getenv("IIAE_FORCE_UPDATE", "").lower() in (
            "true",
            "1",
            "yes",
        )

        # 1. Embeddings (Sentence-Transformers)
        print(f"[Phase 1] Verificando Embeddings: {embedding_model_name}")
        try:
            if is_forced:
                print(f"[Phase 1] Forzando actualización de Embeddings...")
                SentenceTransformer(
                    embedding_model_name,
                    cache_folder=self.cache_dir,
                    token=auth_token,
                    local_files_only=False,
                )
            else:
                try:
                    # Intentamos cargar localmente primero
                    SentenceTransformer(
                        embedding_model_name,
                        cache_folder=self.cache_dir,
                        token=auth_token,
                        local_files_only=True,
                    )
                except Exception:
                    # Fallback si no está en cache
                    print(f"[Phase 1] Embeddings no encontrados en caché. Iniciando descarga...")
                    SentenceTransformer(
                        embedding_model_name,
                        cache_folder=self.cache_dir,
                        token=auth_token,
                        local_files_only=False,
                    )
        except Exception as exc:
            raise SystemExit(f"[Phase 1 Error] Error en Embeddings: {exc}")

        # 2. Oráculo Semántico (NLI)
        print(f"[Phase 1] Verificando Oráculo Semántico (NLI): {entailment_model_name}")
        try:
            if is_forced:
                print(f"[Phase 1] Forzando actualización de NLI...")
                AutoTokenizer.from_pretrained(
                    entailment_model_name,
                    cache_dir=self.cache_dir,
                    token=auth_token,
                    local_files_only=False,
                )
                AutoModelForSequenceClassification.from_pretrained(
                    entailment_model_name,
                    cache_dir=self.cache_dir,
                    token=auth_token,
                    local_files_only=False,
                )
            else:
                try:
                    # Intentamos cargar localmente primero
                    AutoTokenizer.from_pretrained(
                        entailment_model_name,
                        cache_dir=self.cache_dir,
                        token=auth_token,
                        local_files_only=True,
                    )
                    AutoModelForSequenceClassification.from_pretrained(
                        entailment_model_name,
                        cache_dir=self.cache_dir,
                        token=auth_token,
                        local_files_only=True,
                    )
                except (OSError, Exception):
                    # Si falla, descargamos
                    print(f"[Phase 1] Modelo NLI no encontrado en caché. Iniciando descarga...")
                    AutoTokenizer.from_pretrained(
                        entailment_model_name,
                        cache_dir=self.cache_dir,
                        token=auth_token,
                        local_files_only=False,
                    )
                    AutoModelForSequenceClassification.from_pretrained(
                        entailment_model_name,
                        cache_dir=self.cache_dir,
                        token=auth_token,
                        local_files_only=False,
                    )
        except Exception as exc:
            raise SystemExit(f"[Phase 1 Error] Error crítico de carga NLI: {exc}")


if __name__ == "__main__":
    import argparse

    load_dotenv()

    parser = argparse.ArgumentParser(description="Descargador de modelos IIAE")
    parser.add_argument(
        "--force", action="store_true", help="Forzar la descarga/actualización de los modelos"
    )
    args, unknown = parser.parse_known_args()

    downloader = ModelDownloader()
    print("[IIAE] Iniciando secuencia de verificación de modelos...")
    downloader.download_models(force_update=args.force)
    print("[IIAE] Topología de modelos confirmada.")
