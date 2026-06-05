"""
Procesador Determinista de Logits con Multiplexación (MUX) - Fase 3 (Hot Loop).

Intercepta el flujo autoregresivo de logits desde Llama y aplica máscara O(1)
usando la matriz W_bank compilada en Fase 1. Garantiza que la red nunca
asigne probabilidad a tokens prohibidos (se fuerzan a -∞).

Especificación: IDICOC, Sección 3.2 (Contención Determinista)
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple
import numpy as np
import torch
from transformers import LogitsProcessor
from idicoc_notary_core.utils.logger import get_logger

logger = get_logger("audit.logits_processor")


class DeterministicMUXLogitsProcessor(LogitsProcessor):
    """
    Interceptor determinista de logits para contención de políticas.
    [Standard-Zero O(1) Native Masking]
    """

    def __init__(
        self,
        forbidden_token_ids: Optional[Any] = None,
        device: str = "cpu",
        w_bank: Optional[Dict[int, Tuple[str, int]]] = None,
        hard_only: bool = False,
        audit_trace: bool = False,
        cuda_device: Optional[str] = None,
    ) -> None:
        """
        Inicializa el procesador de logits.
        """
        self.hard_only = hard_only
        self.audit_trace = audit_trace
        self.cuda_device = cuda_device or device

        # Compile list of forbidden token IDs
        if forbidden_token_ids is None:
            if w_bank is not None:
                if hard_only:
                    self.forbidden_token_ids = {
                        token_id for token_id, (hardness, _) in w_bank.items() if hardness == "hard"
                    }
                else:
                    self.forbidden_token_ids = set(w_bank.keys())
            else:
                self.forbidden_token_ids = set()
        else:
            self.forbidden_token_ids = set(forbidden_token_ids)

        # Convert to torch tensor on the specified device
        device_to_use = cuda_device or device
        self.mask_tensor = torch.tensor(
            list(self.forbidden_token_ids), device=device_to_use, dtype=torch.long
        )
        # 'mask' alias removed to avoid unused attribute; use mask_tensor directly.

        # Audit logs and stats
        self.intercepts_log: list[Dict] = [] if audit_trace else None
        self.intercepts_count = 0
        self.logits_processed_count = 0

        logger.info(f"[Hot Loop - MUX] Inicializado. Mask size: {len(self.forbidden_token_ids)}")

    def __call__(
        self,
        _input_ids: torch.LongTensor,
        scores: torch.FloatTensor,
    ) -> torch.FloatTensor:
        """
        Máscara de bits O(1) in-place sobre el tensor de logits.
        """
        self.logits_processed_count += 1

        if self.mask_tensor.numel() > 0:
            # Enforce that mask is on the same device as scores
            if self.mask_tensor.device != scores.device:
                raise RuntimeError(
                    f"Device mismatch between MUX mask ({self.mask_tensor.device}) and logits ({scores.device}). "
                    f"All device synchronization must occur before the hot loop to satisfy O(1) latency constraints."
                )

            # Apply in-place -inf masking
            scores[:, self.mask_tensor] = -float("inf")

        if self.audit_trace and self.intercepts_log is not None:
            # Basic stats logging for debugging
            self.intercepts_log.append(
                {
                    "iteration": self.intercepts_count,
                    "forbidden_count": len(self.forbidden_token_ids),
                }
            )
            self.intercepts_count += 1

        return scores

    def process_logits(
        self,
        logits: np.ndarray | torch.Tensor,
        _input_ids: Any = None,
    ) -> Any:
        """
        Legacy/compatibility method for testing.
        """
        is_numpy = isinstance(logits, np.ndarray)
        if is_numpy:
            scores = torch.tensor(logits, dtype=torch.float32)
        else:
            scores = logits

        was_1d = False
        if scores.dim() == 1:
            scores = scores.unsqueeze(0)
            was_1d = True

        scores = self.__call__(None, scores)

        if was_1d:
            scores = scores[0]

        if is_numpy:
            return scores.detach().cpu().numpy()
        return scores

    def get_audit_log(self) -> Optional[list[Dict]]:
        """Retorna el registro de auditoría de interceptiones."""
        return self.intercepts_log.copy() if self.intercepts_log else None

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas de funcionamiento."""
        return {
            "logits_processed": self.logits_processed_count,
            "intercepts_total": self.intercepts_count,
            "forbidden_tokens": len(self.forbidden_token_ids),
            "hard_only_mode": self.hard_only,
            "audit_trace_enabled": self.audit_trace,
        }

    def reset_statistics(self) -> None:
        """Resetea contadores de estadísticas."""
        self.intercepts_count = 0
        self.logits_processed_count = 0
        if self.intercepts_log is not None:
            self.intercepts_log.clear()


class MUXLogitsProcessorFactory:
    """
    Factory para crear y gestionar procesadores de logits.
    """

    _processors: Dict[str, DeterministicMUXLogitsProcessor] = {}

    @classmethod
    def create_or_get(
        cls,
        w_bank: Dict[int, Tuple[str, int]],
        device_key: str = "default",
        hard_only: bool = False,
        audit_trace: bool = False,
        cuda_device: Optional[str] = None,
    ) -> DeterministicMUXLogitsProcessor:
        if device_key not in cls._processors:
            cls._processors[device_key] = DeterministicMUXLogitsProcessor(
                w_bank=w_bank,
                hard_only=hard_only,
                audit_trace=audit_trace,
                cuda_device=cuda_device,
            )
        return cls._processors[device_key]

    @classmethod
    def clear(cls) -> None:
        """Limpia caché de procesadores."""
        cls._processors.clear()


def create_logits_processor_from_policies(
    policies: list[Dict],
    tokenizer: Any,
    embedding_service: Optional[Any] = None,
    hard_only: bool = False,
    audit_trace: bool = False,
) -> Tuple[DeterministicMUXLogitsProcessor, Dict]:
    from idicoc_notary_core.audit.graph.invariant_synthesizer import InvariantSynthesizer

    synthesizer = InvariantSynthesizer(tokenizer, embedding_service)
    w_bank = synthesizer.compile_policies(policies)
    report = synthesizer.get_compilation_report()

    processor = DeterministicMUXLogitsProcessor(
        w_bank=w_bank,
        hard_only=hard_only,
        audit_trace=audit_trace,
    )

    logger.info(
        f"[Hot Loop - Factory] Procesador creado desde políticas. "
        f"W_bank size: {len(w_bank)}, Compilation report: {report}"
    )

    return processor, report
