import json
from typing import Optional
from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph
from .base import GraphCache

class RedisGraphCache(GraphCache):
    """
    Caché distribuida basada en Redis.
    Útil para entornos donde múltiples workers necesitan validar las mismas políticas.
    """

    def __init__(self, redis_url: str, ttl: int = 3600):
        try:
            import redis  # type: ignore
            self.client = redis.from_url(redis_url)
        except ImportError:
            raise RuntimeError("La librería 'redis' no está instalada. Ejecuta 'pip install redis' para usar RedisGraphCache.")
        self.ttl = ttl

    def get(self, key: str) -> Optional[PropertyGraph]:
        data = self.client.get(key)
        if data is None:
            return None
        return PropertyGraph.from_dict(json.loads(data))

    def set(self, key: str, graph: PropertyGraph, ttl: Optional[int] = None) -> None:
        expire_time = ttl if ttl is not None else self.ttl
        self.client.setex(key, expire_time, json.dumps(graph.to_dict()))
