"""
iiae.mao package

Provides MAO engine contract, registry, and lexical fallback implementation.
"""

from .contract import IMAOEngine, MAOReport
from .lexical import LexicalMAOEngine
from .registry import register_engine, get_engine, list_registered_engines
from .composite import CompositeMAOEngine

# Register built‑in engines (lexical already registered lazily in registry)
register_engine("composite", CompositeMAOEngine)

__all__ = [
    "IMAOEngine",
    "MAOReport",
    "register_engine",
    "get_engine",
    "list_registered_engines",
    "LexicalMAOEngine",
    "CompositeMAOEngine",
]
