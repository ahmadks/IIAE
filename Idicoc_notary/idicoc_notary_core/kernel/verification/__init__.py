"""Package verification — ProjectionRegistry e InvariantVerifier.

Note: InvariantVerifier importa desde projection.invariant_state_generator;
para evitar ciclos, se importa de forma diferida si es necesario.
"""

from __future__ import annotations

from .registry import ProjectionRegistry

__all__ = ["ProjectionRegistry", "InvariantVerifier"]


def __getattr__(name: str) -> object:
    if name == "InvariantVerifier":
        from .verifier import InvariantVerifier  # noqa: PLC0415
        return InvariantVerifier
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
