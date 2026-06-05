from __future__ import annotations
from typing import Any

from idicoc_notary_core.audit.llm_interface import BaseLLMProvider


class LlamaProvider(BaseLLMProvider):
    """Provider wrapper for Llama-style local models.

    This module keeps heavy imports local; if the required libraries are not
    installed the provider will raise ImportError when called.
    """

    def __init__(self, model_path: str | None = None, embedding_model_name: str | None = None):
        self.model_path = model_path
        self.embedding_model_name = embedding_model_name
        # Expose an `embedding_provider` attribute consumable by AuditConfig
        self.embedding_provider = None

        try:
            # Lazy import to avoid hard dependency
            from sentence_transformers import SentenceTransformer
            import os

            if embedding_model_name:
                cache_dir = os.getenv("IIAE_CACHE_DIR", "models_cache")
                force_update = os.getenv("IIAE_FORCE_UPDATE", "").lower() in ("true", "1", "yes")

                if force_update:
                    self.embedding_provider = SentenceTransformer(
                        embedding_model_name,
                        cache_folder=cache_dir,
                        local_files_only=False,
                    )
                else:
                    try:
                        self.embedding_provider = SentenceTransformer(
                            embedding_model_name,
                            cache_folder=cache_dir,
                            local_files_only=True,
                        )
                    except Exception:
                        self.embedding_provider = SentenceTransformer(
                            embedding_model_name,
                            cache_folder=cache_dir,
                            local_files_only=False,
                        )
        except Exception:
            self.embedding_provider = None

        # Model instance (lazy)
        self._model = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        
        import os
        is_directory = self.model_path and os.path.isdir(self.model_path)

        if not is_directory:
            try:
                # Try llama-cpp-python first
                from llama_cpp import Llama

                if self.model_path:
                    self._model = Llama(model_path=self.model_path)
                    return
                else:
                    raise RuntimeError("No model_path provided for LlamaProvider")
            except Exception as e:
                # If not a directory and llama-cpp failed, try fallback
                pass

        # Load via transformers AutoModelForCausalLM
        try:
            from transformers import AutoModelForCausalLM
            import torch

            print(f"[LlamaProvider] Cargando modelo transformers desde {self.model_path}...")
            
            # Determine best device and device_map settings
            if torch.cuda.is_available():
                device = torch.device("cuda")
                device_map = "auto"
                torch_dtype = torch.float16
            elif torch.backends.mps.is_available():
                device = torch.device("mps")
                device_map = None # Avoid meta device issues on Apple Silicon
                torch_dtype = torch.float16
            else:
                device = torch.device("cpu")
                device_map = None
                torch_dtype = torch.float32

            self._model = AutoModelForCausalLM.from_pretrained(
                self.model_path,
                device_map=device_map,
                torch_dtype=torch_dtype,
                low_cpu_mem_usage=True,
            )
            
            if device_map is None:
                self._model = self._model.to(device)
                
            print(f"[LlamaProvider] Modelo transformers cargado exitosamente en {device}.")
        except Exception as e:
            raise ImportError(f"Unable to initialize Llama model via transformers or llama-cpp: {e}")

    def generate(self, prompt: str) -> str:
        self._ensure_model()
        try:
            # Check if it is a transformers model
            if hasattr(self._model, "generate"):
                from transformers import AutoTokenizer
                import torch
                tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
                
                # Format prompt simply
                inputs = tokenizer(prompt, return_tensors="pt")
                model_device = next(self._model.parameters()).device
                inputs = {k: v.to(model_device) for k, v in inputs.items() if hasattr(v, "to")}
                
                with torch.no_grad():
                    outputs = self._model.generate(
                        **inputs,
                        max_new_tokens=150,
                        temperature=0.7,
                        do_sample=True,
                        pad_token_id=tokenizer.eos_token_id,
                    )
                
                generated_tokens = outputs[0][inputs["input_ids"].shape[1]:]
                return tokenizer.decode(generated_tokens, skip_special_tokens=True)
            else:
                # Basic generate using llama-cpp-python streaming API
                resp = self._model.generate(prompt)
                if isinstance(resp, dict) and "choices" in resp:
                    return resp["choices"][0]["text"]
                return str(resp)
        except Exception as e:
            raise RuntimeError(f"LlamaProvider.generate failed: {e}")

    def get_embedding(self, text: str) -> list[float]:
        if self.embedding_provider is None:
            raise ImportError("No embedding model available in LlamaProvider")
        vec = self.embedding_provider.encode(text)
        return vec.tolist() if hasattr(vec, "tolist") else list(vec)


__all__ = ["LlamaProvider"]
