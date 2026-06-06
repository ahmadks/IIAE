import os
import pytest
from unittest.mock import patch, MagicMock

# Add root directory to python path
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from providers.phi_provider import PhiProvider


@patch("transformers.AutoModelForCausalLM.from_pretrained")
@patch("transformers.AutoTokenizer.from_pretrained")
@patch("sentence_transformers.SentenceTransformer")
def test_phi_provider_generate_with_mock(mock_st, mock_tok, mock_model_class):
    # Setup mocks
    mock_model = MagicMock()
    mock_model_class.return_value = mock_model
    
    mock_tokenizer = MagicMock()
    mock_tok.return_value = mock_tokenizer
    
    # Mock model parameters to have a device
    mock_param = MagicMock()
    mock_param.device = "cpu"
    mock_model.parameters.return_value = iter([mock_param])
    mock_model.to.return_value = mock_model
    
    # Mock tokenizer outputs
    mock_tokenizer.return_value = {"input_ids": MagicMock()}
    mock_tokenizer.eos_token_id = 50256
    mock_tokenizer.apply_chat_template.return_value = "<user> prompt <assistant>"
    
    # Mock model.generate to return a list of token ids
    mock_outputs = MagicMock()
    # Let outputs be shape [1, 5]
    mock_outputs.__getitem__.return_value = MagicMock()
    mock_model.generate.return_value = mock_outputs
    
    mock_tokenizer.decode.return_value = "Mocked Phi response"
    
    # Instantiate PhiProvider
    provider = PhiProvider(model_path="mock_models_cache/Phi-3.5-mini-instruct")
    
    # Check that model lazy loading works
    provider._ensure_model()
    
    # Test generation
    mock_logits_processor = MagicMock()
    response = provider.generate("Test prompt", logits_processor=mock_logits_processor)
    
    assert response == "Mocked Phi response"
    
    # Verify tokenizer apply_chat_template was called
    mock_tokenizer.apply_chat_template.assert_called_once_with(
        [{"role": "user", "content": "Test prompt"}],
        tokenize=False,
        add_generation_prompt=True
    )
    
    # Verify model.generate was called with our logits processor
    assert mock_model.generate.call_count == 1
    _, kwargs = mock_model.generate.call_args
    assert "logits_processor" in kwargs
    # It wraps it in a LogitsProcessorList
    assert len(kwargs["logits_processor"]) == 1
    assert kwargs["logits_processor"][0] == mock_logits_processor
    assert kwargs["do_sample"] is False
    assert kwargs["max_new_tokens"] == 80


@patch("sentence_transformers.SentenceTransformer")
def test_phi_provider_embedding(mock_st):
    mock_st_instance = MagicMock()
    mock_st.return_value = mock_st_instance
    mock_st_instance.encode.return_value = [0.1, 0.2, 0.3]
    
    provider = PhiProvider(embedding_model_name="test-embedding-model")
    emb = provider.get_embedding("Hello world")
    
    assert emb == [0.1, 0.2, 0.3]
    mock_st_instance.encode.assert_called_once_with("Hello world")
