from __future__ import annotations
from typing import Any
import os

from idicoc_core.utils import BaseLLMProvider

# Enable PyTorch MPS fallback to avoid hangs on unsupported operators
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"


class LocalModelProvider(BaseLLMProvider):
    """Agnostic local LLM provider supporting both GGUF (via llama-cpp-python) and HF transformers.

    Unifies Llama and Phi style models.
    """

    def __init__(
        self,
        model_path: str | None = None,
        embedding_model_name: str | None = None,
        temperature: float = 0.0,
        do_sample: bool = False,
        max_new_tokens: int = 80,
    ):
        self.model_path = model_path
        self.embedding_model_name = embedding_model_name
        self.temperature = temperature
        self.do_sample = do_sample
        self.max_new_tokens = max_new_tokens
        
        # Expose an `embedding_provider` attribute consumable by AuditConfig
        self.embedding_provider = None

        try:
            # Lazy import to avoid hard dependency
            from sentence_transformers import SentenceTransformer

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
        
        if not self.model_path:
            raise RuntimeError("No model_path provided for LocalModelProvider")

        is_directory = os.path.isdir(self.model_path)

        if not is_directory:
            try:
                # Try llama-cpp-python first
                from llama_cpp import Llama
                self._model = Llama(model_path=self.model_path)
                return
            except Exception:
                # If not a directory and llama-cpp failed, try transformers fallback
                pass

        # Load via transformers AutoModelForCausalLM
        try:
            from transformers import AutoModelForCausalLM
            import torch

            print(f"[LocalModelProvider] Cargando modelo transformers desde {self.model_path}...")
            
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
                local_files_only=True,
            )
            
            if device_map is None:
                self._model = self._model.to(device)
                
            print(f"[LocalModelProvider] Modelo transformers cargado exitosamente en {device}.")
        except Exception as e:
            raise ImportError(f"Unable to initialize model via transformers or llama-cpp: {e}")

    def generate(self, prompt: str, **kwargs) -> str:
        self._ensure_model()
        try:
            # Check if it is a transformers model
            if hasattr(self._model, "generate"):
                from transformers import AutoTokenizer, LogitsProcessorList
                import torch
                tokenizer = AutoTokenizer.from_pretrained(self.model_path, local_files_only=True)
                
                # Format prompt using chat template if supported
                try:
                    messages = [{"role": "user", "content": prompt}]
                    prompt_templated = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                except Exception:
                    prompt_templated = prompt
                
                inputs = tokenizer(prompt_templated, return_tensors="pt")
                model_device = next(self._model.parameters()).device
                inputs = {k: v.to(model_device) for k, v in inputs.items() if hasattr(v, "to")}
                
                # Extract override params or fallback to constructor defaults
                gen_kwargs = {
                    "max_new_tokens": kwargs.get("max_new_tokens", self.max_new_tokens),
                    "do_sample": kwargs.get("do_sample", self.do_sample),
                    "pad_token_id": tokenizer.eos_token_id,
                }
                if gen_kwargs["do_sample"]:
                    gen_kwargs["temperature"] = kwargs.get("temperature", self.temperature)

                logits_processor = kwargs.get("logits_processor")
                if logits_processor is not None:
                    gen_kwargs["logits_processor"] = LogitsProcessorList([logits_processor])

                with torch.no_grad():
                    outputs = self._model.generate(
                        **inputs,
                        **gen_kwargs
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
            raise RuntimeError(f"LocalModelProvider.generate failed: {e}")

    def get_embedding(self, text: str) -> list[float]:
        if self.embedding_provider is None:
            raise ImportError("No embedding model available in LocalModelProvider")
        vec = self.embedding_provider.encode(text)
        return vec.tolist() if hasattr(vec, "tolist") else list(vec)


__all__ = ["LocalModelProvider"]
