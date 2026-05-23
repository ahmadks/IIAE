from __future__ import annotations
from typing import Any, Dict, List


class ProjectionRegistry:
    """Registro de proyecciones invariante usado por el núcleo y los wrappers."""

    def __init__(self) -> None:
        self._trace: List[Dict[str, Any]] = []

    def register_projection(self, projection: Dict[str, Any]) -> None:
        self._trace.append(projection)

    def get_projection_trace(self) -> List[Dict[str, Any]]:
        return list(self._trace)

    def clear(self) -> None:
        self._trace.clear()
