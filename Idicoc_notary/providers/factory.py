from __future__ import annotations
from idicoc_notary.utils import BaseLLMProvider


def get_provider(
    provider_type: str,
    model_path: str | None = None,
    embedding_model_name: str | None = None,
    **kwargs
) -> BaseLLMProvider:
    """Factory to get the correct LLM provider dynamically.

    Handles environment/package checking and instantiation.
    """
    provider_type_lower = provider_type.lower()

    if provider_type_lower == "phi":
        try:
            from .phi_provider import PhiProvider
            return PhiProvider(model_path=model_path, embedding_model_name=embedding_model_name)
        except ImportError as e:
            raise ImportError(f"Entorno no preparado: no se pudo cargar PhiProvider debido a dependencias faltantes: {e}")

    elif provider_type_lower == "llama":
        try:
            from .llama_provider import LlamaProvider
            return LlamaProvider(model_path=model_path, embedding_model_name=embedding_model_name)
        except ImportError as e:
            raise ImportError(f"Entorno no preparado: no se pudo cargar LlamaProvider debido a dependencias faltantes: {e}")

    elif provider_type_lower in ("local", "gguf", "transformers"):
        try:
            from .local_provider import LocalModelProvider
            return LocalModelProvider(model_path=model_path, embedding_model_name=embedding_model_name)
        except ImportError as e:
            raise ImportError(f"Entorno no preparado: no se pudo cargar LocalModelProvider debido a dependencias faltantes: {e}")

    elif provider_type_lower == "openai":
        try:
            import openai
        except ImportError as e:
            raise ImportError(f"Entorno no preparado: el paquete 'openai' no está instalado. Detalle: {e}")

        try:
            from .openai_provider import OpenAIProvider
            return OpenAIProvider(
                api_key=kwargs.get("api_key"),
                embedding_model=embedding_model_name or kwargs.get("embedding_model")
            )
        except Exception as e:
            raise ImportError(f"Entorno no preparado: no se pudo instanciar OpenAIProvider: {e}")

    elif provider_type_lower == "anthropic":
        try:
            import anthropic
        except ImportError as e:
            raise ImportError(f"Entorno no preparado: el paquete 'anthropic' no está instalado. Detalle: {e}")

        try:
            from .anthropic_provider import AnthropicProvider
            return AnthropicProvider(
                api_key=kwargs.get("api_key"),
                embedding_model=embedding_model_name or kwargs.get("embedding_model")
            )
        except Exception as e:
            raise ImportError(f"Entorno no preparado: no se pudo instanciar AnthropicProvider: {e}")

    else:
        raise ValueError(f"Proveedor de LLM '{provider_type}' no soportado por la factoría.")
