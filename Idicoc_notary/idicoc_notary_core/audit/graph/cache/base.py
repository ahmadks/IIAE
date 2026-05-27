from typing import Optional
from abc import ABC, abstractmethod
from idicoc_notary_core.kernel.graph.property_graph import PropertyGraph

class GraphCache(ABC):
    """Interfaz abstracta para el almacenamiento en caché del PropertyGraph."""

    @abstractmethod
    def get(self, key: str) -> Optional[PropertyGraph]:
        pass

    @abstractmethod
    def set(self, key: str, graph: PropertyGraph, ttl: int = 3600) -> None:
        pass
