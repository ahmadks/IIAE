import pytest
import numpy as np
from idicoc_notary.isg.graph_manager import PropertyGraph

def test_to_dict_and_from_dict():
    graph = PropertyGraph(embedding_signature="test_sig")
    
    # Add a mock node with a numpy array
    graph.add_policy("ax1", {
        "text": "Hello",
        "embedding": np.array([0.1, 0.2, 0.3])
    })
    
    # Add a mock edge
    graph.add_edge("ax1", "ax2", "entails")
    
    data = graph.to_dict()
    assert data["version"] == 1
    assert data["embedding_signature"] == "test_sig"
    assert "ax1" in data["nodes"]
    
    # Verify numpy array was converted to list
    assert isinstance(data["nodes"]["ax1"]["embedding"], list)
    assert data["nodes"]["ax1"]["embedding"] == [0.1, 0.2, 0.3]
    
    # Reconstruct
    graph2 = PropertyGraph.from_dict(data)
    assert graph2.embedding_signature == "test_sig"
    assert "ax1" in graph2.nodes
    assert len(graph2.edges) == 1
    assert graph2.edges[0]["relation"] == "entails"
