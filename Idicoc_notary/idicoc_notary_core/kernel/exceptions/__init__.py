"""Package exceptions — excepciones del kernel IDICOC."""

from __future__ import annotations

from .alignment_breach import AlignmentBreach
from .integrity_breach import InvariantStateBreach, HardHaltException

__all__ = ["AlignmentBreach", "InvariantStateBreach", "HardHaltException"]
