import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from idicoc_core.dse.evaluator import StructuralDissonanceStrategy, PropertyGraphEvaluator
from idicoc_core.config import AuditConfig
from idicoc_core.pipeline.orchestrator import AuditPipeline
from idicoc_core.isg.graph_manager import PropertyGraph

@pytest.fixture
def strategy():
    config = AuditConfig()
    return StructuralDissonanceStrategy(config)

@patch('idicoc_core.utils.string_utils.StringUtils.to_vector')
@patch('idicoc_core.dse.evaluator._compute_d_1_vectorized')
def test_compute_dissonance_with_property_graph(mock_d1_vec, mock_to_vector, strategy):
    """
    Verifica que StructuralDissonanceStrategy combina correctamente las métricas
    del PropertyGraph (lógicas y temporales) con la disonancia invariante.
    """
    # Mocking embeddings
    mock_to_vector.side_effect = lambda text, **kw: np.array([1.0, 0.0]) if text == "ancla" else np.array([0.0, 1.0])
    
    # Mock graph
    mock_graph = MagicMock()
    mock_graph.evaluate.return_value = 0.8  # d_logic
    mock_graph.compute_temporal.return_value = 0.5  # d_temporal
    
    # Set specific weights
    strategy.lambda_1 = 0.5
    strategy.lambda_2 = 0.4
    strategy.lambda_3 = 0.1
    
    # Mock the EMD calculation internally
    mock_d1_vec.return_value = 0.2
    
    # Mock the PropertyGraphEvaluator methods since the strategy now instantiates it
    with patch('idicoc_core.dse.evaluator.PropertyGraphEvaluator.evaluate', return_value=0.8) as mock_eval, \
         patch('idicoc_core.dse.evaluator.PropertyGraphEvaluator.compute_temporal', return_value=0.5) as mock_temp:
        
        d_s = strategy.compute_dissonance("candidato", "ancla", mock_graph)
        
        # d_s = lambda_inv(0.5) * d_inv(0.2) + lambda_logic(0.4) * d_logic(0.8) + lambda_temporal(0.1) * d_temporal(0.5)
        # d_s = 0.1 + 0.32 + 0.05 = 0.47
        assert abs(d_s - 0.47) < 1e-6
        
        mock_eval.assert_called_once_with("candidato")
        mock_temp.assert_called_once_with("candidato")


@patch('idicoc_core.dse.evaluator.DissonanceStateEvaluator.evaluate')
def test_pipeline_graph_integration(mock_evaluate):
    """
    Verifica que el pipeline delega la ejecución de la disonancia al DQE/Estrategia.
    """
    mock_evaluate.return_value = (0.05, [], {"d_s": 0.05})
    
    config = AuditConfig(
        rigidity_epsilon=0.1,
        ctm_mode="disabled",
        dissonance_weights=(0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0)
    )
    auditor = AuditPipeline(config)
    
    # Ejecutar pipeline
    res = auditor.execute_audit(
        user_prompt="test audit",
        rag_context="context chunk",
        llm_output="test output"
    )
    
    # Lo más importante: D_s se obtuvo del mock
    assert res.dissonance_ds == 0.05
    assert res.is_admitted is True
    mock_evaluate.assert_called_once()
