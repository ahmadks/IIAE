from __future__ import annotations
from typing import Any
from idicoc_notary.api.schemas import SessionContext

class HardwareMask:
    """
    gating/hardware_mask.py
    Checks if context or output is hardware contained (e.g., from an early containment or simulation).
    """

    def __init__(self, config: Any = None):
        self.config = config

    def is_hardware_contained(self, source: Any) -> bool:
        """
        Extraction strategy:
        1. Config-based: if require_hardware_seal is False, always return True
        2. Dict-based: source.get("hardware_contained")
        3. Object attribute: source.hardware_contained
        4. Protocol metadata dict: source.metadata["hardware_contained"] or source.metadata.get("hardware_contained")
        5. In SessionContext.metadata: metadata.get("hardware_contained")
        """
        if self.config and not getattr(self.config, "require_hardware_seal", False):
            return True

        if source is None:
            return False

        # If it is SessionContext
        if isinstance(source, SessionContext):
            if source.metadata and isinstance(source.metadata, dict):
                return bool(source.metadata.get("hardware_contained", False))
            # Fallback check on prompts or other details if any
            return False

        # 1. Dict-based payload
        if isinstance(source, dict):
            return bool(source.get("hardware_contained", False))

        # 2. Direct attribute
        hw = getattr(source, "hardware_contained", None)
        if hw is not None:
            return bool(hw)

        # 3. Protocol metadata dict
        meta = getattr(source, "metadata", None)
        if isinstance(meta, dict):
            return bool(meta.get("hardware_contained", False))

        return False
