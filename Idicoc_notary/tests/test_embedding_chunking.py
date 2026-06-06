import pytest
import numpy as np
from idicoc_notary.utils.string_utils import StringUtils

def test_embedding_token_limit_and_chunking():
    """Verify that passing moderately long text raises a warning and does chunking."""
    long_text = "hello world " * 800
    
    with pytest.warns(UserWarning, match="El texto de entrada supera el límite de tokens"):
        embedding = StringUtils.embed_text(long_text, max_chunks=20)
        
    assert isinstance(embedding, np.ndarray)
    assert np.allclose(np.linalg.norm(embedding), 1.0, atol=1e-5)

def test_embedding_max_chunks_limit():
    """Verify that text exceeding embedding_max_chunks raises a ValueError."""
    giant_text = "extremely long sentence " * 2000
    
    with pytest.raises(ValueError, match="superando el límite permitido"):
        StringUtils.embed_text(giant_text, max_chunks=3)
