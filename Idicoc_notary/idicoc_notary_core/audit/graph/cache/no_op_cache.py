import json
from typing import Optional
from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph
from .base import GraphCache

class NoOpGraphCache(GraphCache):
    """Caché en memoria básica (o No-Op para entornos distribuidos locales)."""

    def __init__(self):
        self._store = {}

    def get(self, key: str) -> Optional[PropertyGraph]:
        if key in self._store:
            data = self._store[key]
            # Usar from_dict para asegurar que se retorna una nueva instancia 
            # sin mutar la versión en caché.
            return PropertyGraph.from_dict(json.loads(data))
        return None

    def set(self, key: str, graph: PropertyGraph, ttl: int = 3600) -> None:
        # En memoria simplemente serializamos y guardamos
        self._store[key] = json.dumps(graph.to_dict())
