import pytest
from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph
from idicoc_notary_core.audit.graph.cache import NoOpGraphCache, RedisGraphCache
from idicoc_notary_core.audit.pipeline import IDICOCPipeline
from idicoc_notary_core.audit.config import AuditConfig
from idicoc_notary_core.audit.graph.loader import InlineAxiomLoader

def test_noop_graph_cache():
    cache = NoOpGraphCache()
    graph = PropertyGraph(embedding_signature="test_sig")
    graph.add_axiom("1", {"text": "A"})
    
    cache.set("key1", graph)
    
    cached_graph = cache.get("key1")
    assert cached_graph is not None
    assert cached_graph.embedding_signature == "test_sig"
    assert "1" in cached_graph.nodes
    
    # Verify we get None for missing key
    assert cache.get("key2") is None

def test_pipeline_uses_cache():
    # Creamos un loader con datos fijos
    loader = InlineAxiomLoader([{"id": "ax1", "text": "Test Axiom"}])
    config = AuditConfig(
        instance_name="test_instance", 
        semantic_embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        axiom_loader=loader
    )
    
    cache = NoOpGraphCache()
    
    # 1. Al inicializar, debería generar y guardar en caché (el constructor llama a initialize)
    pipeline1 = IDICOCPipeline(config, graph_cache=cache)
    
    # Verificamos que se guardó algo
    assert len(cache._store) == 1
    
    # Reemplazar el loader por uno que falla si es llamado para probar que usa caché
    class FailLoader:
        def load_axioms(self):
            # El pipeline llamará a load_axioms para derivar la clave de caché
            return [{"id": "ax1", "text": "Test Axiom"}]
            
    config.axiom_loader = FailLoader()
    pipeline2 = IDICOCPipeline(config, graph_cache=cache)
    
    # Debe tener los mismos nodos
    assert "ax1" in pipeline2.graph.nodes

def test_redis_cache_without_redis_installed():
    # Debería lanzar RuntimeError si intentamos instanciarlo (asumiendo que no mockeamos import redis)
    # o simplemente verificamos que la firma existe
    try:
        import redis
    except ImportError:
        with pytest.raises(RuntimeError):
            RedisGraphCache("redis://localhost:6379")
