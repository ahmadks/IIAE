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
    def embed_text(
        cls,
        text: str,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        max_chunks: int = 10,
    ) -> np.ndarray:
        """Convierte texto a un vector usando el modelo de embeddings.

        Parameters:
            text (str): El texto a procesar.
            model_name (str): Nombre del modelo a utilizar.
            max_chunks (int): Límite máximo de chunks permitidos para proteger los recursos.

        Returns:
            np.ndarray: Vector numérico que representa el texto.
        """
        model = cls.get_embedding_model(model_name)

        if model is not None:
            max_len = getattr(model, "max_seq_length", 512)
            if max_len is None:
                max_len = 512

            # 1. Determinar si el texto supera el límite de tokens
            tokenizer = getattr(model, "tokenizer", None)
            tokens = []
            has_exceeded = False

            if tokenizer is not None:
                try:
                    tokens = tokenizer.encode(text, add_special_tokens=False)
                    if len(tokens) > max_len:
                        has_exceeded = True
                except Exception:
                    # Fallback si falla la tokenización
                    if len(text) > max_len * 4:
                        has_exceeded = True
            else:
                if len(text) > max_len * 4:
                    has_exceeded = True

            # 2. Si se supera el límite de tokens, emitir warning y aplicar chunking
            if has_exceeded:
                import warnings
                import logging

                num_tokens = len(tokens) if tokens else int(len(text) / 4)
                warn_msg = (
                    f"WARNING: El texto de entrada supera el límite de tokens del modelo de embeddings "
                    f"({num_tokens} tokens detectados > límite de {max_len} tokens para '{model_name}'). "
                    f"Se activará el mecanismo de chunking automático para evitar que se trunque "
                    f"silenciosamente el texto final y se pierda información en el cálculo de disonancia."
                )
                warnings.warn(warn_msg, UserWarning)
                logger = logging.getLogger("kernel.embedding_service")
                logger.warning(warn_msg)

                # Segmentación (chunking) determinista usando ventanas de tamaño max_len - 2 (para tokens especiales)
                chunks = []
                if tokenizer is not None and tokens:
                    # Reservamos margen de 2 tokens para caracteres especiales ([CLS] y [SEP])
                    chunk_size = max_len - 2 if max_len > 2 else max_len
                    for i in range(0, len(tokens), chunk_size):
                        chunk_tokens = tokens[i : i + chunk_size]
                        chunk_text = tokenizer.decode(chunk_tokens, skip_special_tokens=True)
                        if chunk_text.strip():
                            chunks.append(chunk_text)
                else:
                    # Fallback segmentando por palabras
                    words = text.split()
                    chunk_size_words = int((max_len - 2) * 0.75)
                    if chunk_size_words < 1:
                        chunk_size_words = 1
                    for i in range(0, len(words), chunk_size_words):
                        chunk_text = " ".join(words[i : i + chunk_size_words])
                        if chunk_text.strip():
                            chunks.append(chunk_text)

                # Validar límite máximo de chunks para proteger de explosión de cómputo
                if len(chunks) > max_chunks:
                    raise ValueError(
                        f"El texto de entrada es extremadamente largo y genera {len(chunks)} chunks, "
                        f"superando el límite permitido de {max_chunks} chunks."
                    )

                # 3. Obtener embeddings individuales y promediar
                chunk_embeddings = []
                for chunk in chunks:
                    emb = model.encode(chunk)
                    chunk_embeddings.append(np.asarray(emb, dtype=float))

                if chunk_embeddings:
                    aggregated = np.mean(chunk_embeddings, axis=0)
                    # Normalizar resultado agregado a norma unidad para coherencia
                    norm = float(np.linalg.norm(aggregated))
                    if norm > 1e-12:
                        aggregated = aggregated / norm
                    return aggregated

            # Codificación directa; normalizar salida a norma unidad para coherencia
            embedding = model.encode(text)
            embedding = np.asarray(embedding, dtype=float)
            norm = float(np.linalg.norm(embedding))
            if norm > 1e-12:
                embedding = embedding / norm
            return embedding

        # Fallback pseudo-determinista si el modelo no está disponible
        import hashlib

        h = hashlib.sha256(text.encode("utf-8")).digest()
        dim = cls.get_embedding_dimension(model_name)
        fallback = np.zeros(dim, dtype=float)
        for i in range(min(dim, len(h))):
            fallback[i] = float(h[i]) / 255.0

        return fallback

    @classmethod
    def get_embedding_dimension(
        cls, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    ) -> int:
        """Devuelve la dimensión de salida del modelo de embeddings si es disponible."""
        model = cls.get_embedding_model(model_name)
        try:
            if model is not None and hasattr(model, "get_sentence_embedding_dimension"):
                return int(model.get_sentence_embedding_dimension())
        except Exception:
            pass
        return 384

    @classmethod
    def to_vector(
        cls,
        y: Any,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        max_chunks: int = 10,
    ) -> np.ndarray:
        """Convierte cualquier entrada a un vector numérico (ndarray)."""
        if isinstance(y, str):
            return cls.embed_text(y, model_name, max_chunks=max_chunks)

        # Si ya es un array o lista, devolverlo como ndarray
        try:
            arr = np.asarray(
                getattr(y, "distribution", getattr(y, "measure_vector", y)), dtype=float
            )
            if arr.ndim == 1 and arr.size > 0:
                return arr
        except Exception:
            pass

        # Fallback final
        return cls.embed_text(str(y), model_name, max_chunks=max_chunks)
