"""Mocks compartidos para pruebas unitarias del auditor IDICOC."""

from __future__ import annotations
from typing import Any
import re


class BankEntropyAnalyzer:
    """Ejemplo mínimo de analizador de entropía específico para banca."""

    def measure_entropy(self, raw_input: Any) -> float:
        if raw_input is None:
            return 1.0
        text = str(raw_input)
        non_alpha = sum(1 for c in text if not c.isalnum() and not c.isspace())
        return min(1.0, non_alpha / max(1, len(text)))

    def decompose(self, raw_input: Any) -> tuple[str, Any]:
        text = str(raw_input)
        structural = re.sub(r"\b\d{10,}\b", "[CUENTA]", text)
        noise = re.findall(r"\b\d{10,}\b", text)
        return structural, noise

    def is_recoverable(self, noise_component: Any) -> bool:
        return bool(noise_component)
