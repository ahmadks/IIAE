import os
import pytest
from unittest.mock import patch, MagicMock

# Import components
from idicoc_notary.utils.model_downloader import ModelDownloader
from idicoc_notary.utils.embedding_service import EmbeddingService
from providers.model_downloader import ensure_phi_downloaded
from providers.phi_provider import PhiProvider
from idicoc_notary.config import AuditConfig


@patch("sentence_transformers.SentenceTransformer")
@patch("transformers.AutoTokenizer.from_pretrained")
@patch("transformers.AutoModelForSequenceClassification.from_pretrained")
def test_model_downloader_respects_cache(mock_model, mock_tok, mock_st):
    downloader = ModelDownloader(cache_dir="test_models_cache")
    
    # Test standard download (not forced)
    # Since they are cached, local_files_only=True should be called and succeed
    downloader.download_models(force_update=False)
    
    # SentenceTransformer called with local_files_only=True
    _, kwargs_st = mock_st.call_args
    assert kwargs_st["local_files_only"] is True
    assert kwargs_st["cache_folder"] == "test_models_cache"

    # Tokenizer/Classifier called with local_files_only=True
    _, kwargs_tok = mock_tok.call_args
    assert kwargs_tok["local_files_only"] is True
    assert kwargs_tok["cache_dir"] == "test_models_cache"

    _, kwargs_model = mock_model.call_args
    assert kwargs_model["local_files_only"] is True
    assert kwargs_model["cache_dir"] == "test_models_cache"


@patch("sentence_transformers.SentenceTransformer")
@patch("transformers.AutoTokenizer.from_pretrained")
@patch("transformers.AutoModelForSequenceClassification.from_pretrained")
def test_model_downloader_respects_force_update(mock_model, mock_tok, mock_st):
    downloader = ModelDownloader(cache_dir="test_models_cache")
    
    # Test forced update
    downloader.download_models(force_update=True)
    
    _, kwargs_st = mock_st.call_args
    assert kwargs_st["local_files_only"] is False
 
    _, kwargs_tok = mock_tok.call_args
    assert kwargs_tok["local_files_only"] is False
 
    _, kwargs_model = mock_model.call_args
    assert kwargs_model["local_files_only"] is False
 
 
@patch("huggingface_hub.snapshot_download")
@patch("providers.model_downloader.Path")
def test_ensure_phi_downloaded_respects_cache(mock_path, mock_snapshot):
    # Mock Path constructor and parent-child target folder structure
    mock_parent = MagicMock()
    mock_target_dir = MagicMock()
    mock_parent.__truediv__.return_value = mock_target_dir
    mock_path.return_value = mock_parent
    
    # local_target_dir properties
    mock_target_dir.exists.return_value = True
    mock_target_dir.iterdir.return_value = [MagicMock()] # non-empty
    mock_target_dir.glob.return_value = [MagicMock()] # non-empty weight files list
    
    # Subpath calls (like index or .cache) return mock_subpath which does not exist
    mock_subpath = MagicMock()
    mock_subpath.exists.return_value = False
    mock_subpath.__truediv__.return_value = mock_subpath
    mock_target_dir.__truediv__.return_value = mock_subpath

    # Test Phi downloader uses local_files_only=True first
    ensure_phi_downloaded(cache_dir="test_models_cache", force_update=False)
    
    # Verify snapshot_download was called with local_files_only=True
    assert mock_snapshot.call_count == 1
    _, kwargs = mock_snapshot.call_args
    assert kwargs["local_files_only"] is True
    assert kwargs["repo_id"] == "microsoft/Phi-3.5-mini-instruct"

 
 
@patch("huggingface_hub.snapshot_download")
def test_ensure_phi_downloaded_forced(mock_snapshot):
    # Test Phi downloader with force_update=True
    ensure_phi_downloaded(cache_dir="test_models_cache", force_update=True)
    
    assert mock_snapshot.call_count == 1
    _, kwargs = mock_snapshot.call_args
    assert kwargs["local_files_only"] is False
 
 
@patch("sentence_transformers.SentenceTransformer")
def test_embedding_service_respects_cache(mock_st):
    service = EmbeddingService()
    service.clear_cache()
    
    # Call get_embedder (standard, not forced)
    service.get_embedder("test-model")
    
    _, kwargs = mock_st.call_args
    assert kwargs["local_files_only"] is True
    assert kwargs["cache_folder"] == "models_cache"
 
 
@patch("sentence_transformers.SentenceTransformer")
def test_phi_provider_respects_cache(mock_st):
    provider = PhiProvider(embedding_model_name="test-model")
    
    _, kwargs = mock_st.call_args
    assert kwargs["local_files_only"] is True
    assert kwargs["cache_folder"] == "models_cache"
