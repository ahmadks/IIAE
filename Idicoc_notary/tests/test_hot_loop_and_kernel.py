import numpy as np
import pytest

from idicoc_core.dse.evaluator import DeterministicMUXLogitsProcessor
from idicoc_core.isg.loader import InvariantSynthesizer


class DummyTokenizer:
    def __init__(self):
        self._vocab = {}

    def __len__(self):
        return 1000

    def encode(self, text, add_special_tokens=False):
        token_ids = []
        for word in str(text).split():
            if word not in self._vocab:
                self._vocab[word] = len(self._vocab) + 1
            token_ids.append(self._vocab[word])
        return token_ids

    def decode(self, token_ids):
        reverse = {v: k for k, v in self._vocab.items()}
        return " ".join(reverse.get(token_id, f"<UNK:{token_id}>") for token_id in token_ids)

    def get_vocab(self) -> dict:
        """Required by _get_or_compute_vocab_embeddings to build the KDTree."""
        return dict(self._vocab)


class DummyEmbeddingService:
    """Servicio de embeddings determinista basado en frecuencia de caracteres (32 dims).

    Soporta tanto encoding escalar (texto → vector) como batch (lista de textos → matriz).
    Requerido por _get_or_compute_vocab_embeddings, que pasa una lista de tokens al encoder.
    """

    def encode(self, text, model_name=None):
        if isinstance(text, list):
            # Batch encoding: devuelve una matriz (N, 32) — una fila por elemento
            return np.asarray([self._encode_single(t) for t in text], dtype=float)
        return self._encode_single(text)

    def _encode_single(self, text: str) -> np.ndarray:
        """Codifica un texto como vector de frecuencia de caracteres normalizado (32 dims)."""
        vec = np.zeros(32, dtype=float)
        for ch in str(text).lower():
            vec[ord(ch) % 32] += 1.0
        norm = np.linalg.norm(vec)
        return vec / norm if norm > 1e-12 else vec


@pytest.mark.parametrize("use_torch", [False, True])
def test_logits_processor_masks_forbidden_tokens(use_torch):
    processor = DeterministicMUXLogitsProcessor(
        w_bank={1: ("soft", 1), 3: ("hard", 2)}, hard_only=False
    )
    logits = np.array([0.5, 0.1, 0.2, 0.3], dtype=float)

    if use_torch:
        try:
            import torch

            logits = torch.tensor(logits, dtype=torch.float32)
        except ImportError:
            pytest.skip("Torch no disponible para este entorno")

    masked = processor.process_logits(logits)
    masked_tensor = None
    if use_torch:
        import torch

        assert isinstance(masked, torch.Tensor)
        masked_tensor = masked
        masked = masked.detach().cpu().numpy()
    assert masked.shape == (4,)
    if use_torch:
        import torch

        assert torch.isneginf(masked_tensor[1])
        assert torch.isneginf(masked_tensor[3])
    else:
        assert np.isneginf(masked[1])
        assert np.isneginf(masked[3])
    assert masked[0] == pytest.approx(0.5)
    assert masked[2] == pytest.approx(0.2)


def test_invariant_synthesizer_extracts_semantic_concepts():
    """Verifica que el InvariantSynthesizer extrae tokens via KDTree geométrico.

    Con la arquitectura puramente geométrica, el filtrado de stopwords
    se realiza implícitamente por distancia semántica, no por diccionarios lingüísticos.
    Este test usa embedding_threshold=0.0 para incluir todo el vocabulario (radio máximo)
    y verificar el plumbing del KDTree: que el grafo del vocabulario se construye, los
    tokens se indexan y la consulta devuelve resultados correctamente.
    """
    tokenizer = DummyTokenizer()
    embedding_service = DummyEmbeddingService()

    # Pre-poblar el vocabulario con las palabras de la política para que el KDTree
    # tenga tokens que indexar. En producción, el tokenizador Llama ya tiene su vocab completo.
    policy_text = "no repetir los datos confidenciales del cliente"
    for word in policy_text.split():
        tokenizer.encode(word)  # Registra cada palabra en _vocab

    # Crear el sintetizador con precompute_vocab_embeddings=True para construir el KDTree.
    # threshold=0.0 → radio = sqrt(2): todos los tokens del vocab pasan la consulta,
    # lo que nos permite verificar el plumbing geométrico con embeddings deterministas.
    synthesizer = InvariantSynthesizer(
        tokenizer,
        embedding_service=embedding_service,
        precompute_vocab_embeddings=True,
        embedding_threshold=0.0,
    )

    report = synthesizer.compile_policies(
        [
            {
                "text": policy_text,
                "hardness": "hard",
                "priority": 5,
            }
        ]
    )

    # Invariante 1: el W_bank debe ser no-vacío (el KDTree encontró tokens dentro del radio)
    assert report, "W_bank debe contener al menos un token tras la consulta geométrica"

    token_ids = sorted(report.keys())
    assert len(token_ids) > 0

    # Invariante 2: todos los token_ids del reporte deben estar en el vocabulario del tokenizador
    vocab = tokenizer.get_vocab()
    valid_ids = set(vocab.values())
    for tid in token_ids:
        assert tid in valid_ids, f"token_id={tid} no está en el vocabulario del tokenizador"

    # Invariante 3: los tokens son decodificables correctamente
    token_texts = [synthesizer.tokenizer.decode([token_id]) for token_id in token_ids]
    assert all(
        isinstance(t, str) and len(t) > 0 for t in token_texts
    ), "Todos los tokens del W_bank deben decodificarse como strings no vacíos"
