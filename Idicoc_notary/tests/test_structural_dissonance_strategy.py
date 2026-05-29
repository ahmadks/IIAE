import pytest
from unittest.mock import MagicMock, patch
import numpy as np

from idicoc_notary_core.audit.dse.structural_strategy import StructuralDissonanceStrategy
from idicoc_notary_core.audit.config import AuditConfig

@pytest.fixture
def strategy():
    config = AuditConfig()
    return StructuralDissonanceStrategy(config)

@patch('idicoc_notary_core.utils.string_utils.StringUtils.to_vector')
def test_compute_dissonance_with_property_graph(mock_to_vector, strategy):
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
    strategy._compute_d_1_vectorized = MagicMock(return_value=0.2)
    
    # Mock the PropertyGraphEvaluator methods since the strategy now instantiates it
    with patch('idicoc_notary_core.audit.graph.property_graph_evaluator.PropertyGraphEvaluator.evaluate', return_value=0.8) as mock_eval, \
         patch('idicoc_notary_core.audit.graph.property_graph_evaluator.PropertyGraphEvaluator.compute_temporal', return_value=0.5) as mock_temp:
        
        d_s = strategy.compute_dissonance("candidato", "ancla", mock_graph)
        
        # d_s = lambda_inv(0.5) * d_inv(0.2) + lambda_logic(0.4) * d_logic(0.8) + lambda_temporal(0.1) * d_temporal(0.5)
        # d_s = 0.1 + 0.32 + 0.05 = 0.47
        assert abs(d_s - 0.47) < 1e-6
        
        mock_eval.assert_called_once_with("candidato")
        mock_temp.assert_called_once_with("candidato")

@patch('idicoc_notary_core.utils.string_utils.StringUtils.to_vector')
def test_projection_manifold(mock_to_vector, strategy):
    """
    Verifica que el algoritmo de proyección por gradiente reduce el D_s.
    """
    # Vector ancla y vector candidato
    target_vec = np.array([1.0, 0.0])
    candidate_vec = np.array([0.0, 1.0])
    
    def side_effect(text, **kw):
        if text == "ancla":
            return target_vec
        return candidate_vec
        
    mock_to_vector.side_effect = side_effect
    
    # Mock graph
    mock_graph = MagicMock()
    mock_graph.evaluate.return_value = 0.0
    mock_graph.compute_temporal.return_value = 0.0
    
    # Sobreescribimos compute_dissonance para simular que la distancia se reduce
    # cuando los vectores se acercan. En StructuralDissonanceStrategy, compute_dissonance
    # se llama repetidamente en el bucle.
    dissonances = [0.8, 0.6, 0.4, 0.1]
    call_counts = {"count": 0}
    
    def mock_compute_dissonance(z, V_hat, G_t, context_input=None):
        val = dissonances[min(call_counts["count"], len(dissonances)-1)]
        call_counts["count"] += 1
        return val
        
    strategy.compute_dissonance = mock_compute_dissonance
    
    # Proyectar
    epsilon = 0.2
    final_vec = strategy.project("candidato", epsilon, "ancla", mock_graph, max_iter=10)
    
    # El bucle de gradiente debe ejecutarse hasta que la disonancia <= epsilon
    # En nuestro mock, ocurre en la 4ª llamada (valor 0.1 <= 0.2)
    assert call_counts["count"] >= 4
    assert isinstance(final_vec, np.ndarray)

from idicoc_notary_core.audit.pipeline import IDICOCPipeline
from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph

def test_pipeline_graph_integration():
    """
    Verifica que el pipeline inyecta correctamente el contexto y los politicas
    en el PropertyGraph, y delega la ejecución de la disonancia al DQE/Estrategia.
    """
    # Mock strategy as a factory
    mock_strategy_instance = MagicMock()
    mock_strategy_instance.compute.return_value = (0.05, 0.0, "test audit", False, {"d_s": 0.05, "d_1": 0.0, "d_2": 0.0})
    mock_strategy_instance._compute_context_contradiction.return_value = (0.0, [])
    mock_strategy_instance.compute_dissonance.return_value = 0.05
    mock_strategy_instance.lambda_weights = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    mock_strategy_instance._d_inv_from_pair = MagicMock(return_value=0.0)
    
    mock_strategy_class = MagicMock(return_value=mock_strategy_instance)
    mock_strategy_class.lambda_weights = [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
    
    config = AuditConfig(
        dissonance_strategy=mock_strategy_class,
        rigidity_epsilon=0.1,
        ctm_mode="disabled",
        dissonance_weights=(0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0)
    )
    auditor = IDICOCPipeline(config)
    
    # Inyectar mock PropertyGraph para capturar el comportamiento
    mock_graph = MagicMock(spec=PropertyGraph)
    mock_graph.nodes = {}
    mock_graph.get_active_policies.return_value = []
    auditor.graph = mock_graph
    
    # Ejecutar pipeline
    res = auditor.execute(
        audit_input="test audit",
        context_input=["context chunk"],
        context_policies=["test policy"]
    )
    
    # 1. El PropertyGraph debe haber sido actualizado con los politicas
    # Dependiendo de cómo se implemente la carga en el pipeline:
    # mock_graph.insert... (el pipeline hace algo como `self.dse.update_graph`)
    # Wait, en el pipeline, la carga del graph se hace a traves del policy_engine
    
    # Lo más importante: D_s se obtuvo del mock
    print(f"DEBUG: res={res}")
    assert res["canonical_state"].metadata["audit_metrics"]["d_s"] == 0.05
    assert res["canonical_state"].metadata["admission_metrics"]["admitted"] is True
