from typing import Type, Dict, Any
import threading

from .contract import IMAOEngine

# Internal mutable registry mapping engine name -> engine class
_ENGINE_REGISTRY: Dict[str, Type[IMAOEngine]] = {}
_REGISTRY_LOCK = threading.RLock()

_REQUIRED_METHODS = (
    "material_causality",
    "axiomatic_invariance",
    "probability_entropy",
    "geoclimatic_synchrony",
)


def _implements_mao(engine_cls: Type[IMAOEngine]) -> bool:
    return all(
        hasattr(engine_cls, m) and callable(getattr(engine_cls, m))
        for m in _REQUIRED_METHODS
    )


def register_engine(name: str, engine_cls: Type[IMAOEngine]) -> None:
    """Register a custom MAO engine under a unique name.

    If ``name`` is already present, a ``RuntimeError`` is raised to avoid accidental
    overwriting of engines supplied by third‑party libraries.
    """
    if not _implements_mao(engine_cls):
        raise TypeError(
            "engine_cls must implement all Annex V filters: "
            "material_causality, axiomatic_invariance, "
            "probability_entropy, geoclimatic_synchrony"
        )
    with _REGISTRY_LOCK:
        if name in _ENGINE_REGISTRY:
            raise RuntimeError(f"MAO engine '{name}' is already registered")
        _ENGINE_REGISTRY[name] = engine_cls


def _register_default_engine() -> None:
    """Register the built‑in lexical engine under the name 'lexical'."""
    from .lexical import LexicalMAOEngine
    register_engine("lexical", LexicalMAOEngine)

# Ensure the default engine is available on import
_register_default_engine()

def get_engine(name: str, **params) -> IMAOEngine:
    """Instantiate a registered engine with the provided parameters.

    Raises:
        ValueError: If ``name`` is not present in the registry.
    """
    with _REGISTRY_LOCK:
        try:
            engine_cls = _ENGINE_REGISTRY[name]
        except KeyError as exc:
            raise ValueError(f"MAO engine '{name}' not registered") from exc
        return engine_cls(**params)

def list_registered_engines() -> Dict[str, Dict[str, Any]]:
    """Return a shallow copy of the registry with engine class and docstring for introspection/debugging."""
    with _REGISTRY_LOCK:
        return {name: {"class": cls, "doc": cls.__doc__} for name, cls in _ENGINE_REGISTRY.items()}

# Backward compatibility: expose built‑in exception types
RuntimeError = RuntimeError
ValueError = ValueError
