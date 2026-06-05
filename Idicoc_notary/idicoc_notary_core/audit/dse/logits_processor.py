"""
Procesador Determinista de Logits con Multiplexación (MUX) - Fase 3 (Hot Loop).

Intercepta el flujo autoregresivo de logits desde Llama y aplica máscara O(1)
usando la matriz W_bank compilada en Fase 1. Garantiza que la red nunca
asigne probabilidad a tokens prohibidos (se fuerzan a -∞).

Especificación: IDICOC Standard-Zero, Sección 3.2 (Contención Determinista)
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple
import numpy as np
from idicoc_notary_core.utils.logger import get_logger

logger = get_logger("audit.logits_processor")


class DeterministicMUXLogitsProcessor:
    """
    Interceptor determinista de logits para contención de políticas.

    Diseño:
    - Se inyecta en la llamada `model.generate()` de Llama
    - Por cada iteración (token generado), intercept(input_ids, logits)
    - Aplica máscara: logits[forbidden_token_id] = -∞
    - Complejidad: O(n_forbidden) por iteración → O(1) amortizado con bitset

    Parámetros:
    - w_bank: matriz indexada {token_id: (hardness, priority)}
    - hard_only: si True, solo bloquea tokens "hard" (permite "soft")
    - audit_trace: si True, registra cada interceptión para auditoría
    """

    def __init__(
        self,
        w_bank: Dict[int, Tuple[str, int]],
        hard_only: bool = False,
        audit_trace: bool = False,
        cuda_device: Optional[str] = None,
    ) -> None:
        """
        Inicializa el procesador de logits.

        Args:
            w_bank: Matriz de tokens prohibidos compilada por InvariantSynthesizer
            hard_only: Si True, solo bloquea tokens "hard" (default: False = bloquear todos)
            audit_trace: Si True, registra interceptiones (default: False = rendimiento)
            cuda_device: Dispositivo CUDA si está disponible ("cuda:0", etc.)
        """
        self.w_bank = w_bank
        self.hard_only = hard_only
        self.audit_trace = audit_trace
        self.cuda_device = cuda_device

        # Compilar conjunto de tokens prohibidos
        if hard_only:
            self.forbidden_token_ids = {
                token_id for token_id, (hardness, _) in w_bank.items() if hardness == "hard"
            }
            logger.info(
                f"[Hot Loop - Logits Processor] Hard-only mode activado. "
                f"Tokens bloqueados (hard): {len(self.forbidden_token_ids)}"
            )
        else:
            self.forbidden_token_ids = set(w_bank.keys())
            logger.info(
                f"[Hot Loop - Logits Processor] All-policies mode activado. "
                f"Tokens bloqueados totales: {len(self.forbidden_token_ids)}"
            )

        # Auditoría de interceptiones (bajo demanda)
        self.intercepts_log: list[Dict] = [] if audit_trace else None
        self.intercepts_count = 0
        self.logits_processed_count = 0

        logger.info(
            f"[Hot Loop - MUX] Inicializado. Vocabulario: "
            f"vocab_size estimado, Mask size: {len(self.forbidden_token_ids)}"
        )

    def __call__(
        self,
        input_ids: np.ndarray | None,
        logits: np.ndarray,
    ) -> np.ndarray:
        """
        Interfaz compatible con transformers.generation.LogitsProcessor.

        Args:
            input_ids: IDs de tokens generados hasta ahora (opcional)
            logits: Tensor de logits [vocab_size] o [batch, vocab_size]

        Returns:
            Logits modificados con tokens prohibidos forzados a -∞
        """
        return self.process_logits(logits, input_ids)

    def process_logits(
        self,
        logits: np.ndarray | Any,
        input_ids: np.ndarray | Any | None = None,
    ) -> Any:
        """
        Aplica máscara O(1) a logits interceptados.

        Estrategia:
        1. Inicializar máscara = zeros
        2. Para cada token_id en forbidden: máscara[token_id] = -∞
        3. logits_masked = logits + máscara

        Args:
            logits: Array o tensor [vocab_size] o [batch_size, vocab_size]
            input_ids: Array o tensor de tokens previos (para auditoría)

        Returns:
            Logits modificados
        """
        self.logits_processed_count += 1

        use_torch = False
        torch = None
        try:
            import torch

            if hasattr(logits, "to") and hasattr(logits, "dtype"):
                use_torch = True
        except ImportError:
            torch = None

        if use_torch:
            if logits.dim() == 1:
                logits = logits.unsqueeze(0)
                was_1d = True
            else:
                was_1d = False

            batch_size, vocab_size = logits.shape
            mask = torch.zeros_like(logits)

            if self.forbidden_token_ids:
                token_ids = torch.tensor(
                    sorted(self.forbidden_token_ids),
                    dtype=torch.long,
                    device=logits.device,
                )
                valid = (token_ids >= 0) & (token_ids < vocab_size)
                token_ids = token_ids[valid]
                if token_ids.numel() > 0:
                    mask[:, token_ids] = torch.tensor(
                        -1e10, dtype=logits.dtype, device=logits.device
                    )

            logits_masked = logits + mask

            if self.audit_trace and self.intercepts_log is not None:
                max_before = float(torch.max(logits).detach().cpu().item())
                max_after = float(torch.max(logits_masked).detach().cpu().item())
                min_before = float(torch.min(logits).detach().cpu().item())
                min_after = float(torch.min(logits_masked).detach().cpu().item())
                intercept_record = {
                    "iteration": self.intercepts_count,
                    "vocab_size": vocab_size,
                    "forbidden_count": len(self.forbidden_token_ids),
                    "max_logit_before": max_before,
                    "max_logit_after": max_after,
                    "min_logit_before": min_before,
                    "min_logit_after": min_after,
                }

                if (
                    input_ids is not None
                    and hasattr(input_ids, "shape")
                    and len(input_ids.shape) > 0
                ):
                    last_token = input_ids[-1] if len(input_ids) > 0 else -1
                    intercept_record["last_token_id"] = int(last_token)

                self.intercepts_log.append(intercept_record)
                self.intercepts_count += 1

            if was_1d:
                logits_masked = logits_masked[0]

            return logits_masked

        # Fallback numpy path for compatibility si torch no está disponible
        if isinstance(logits, np.ndarray):
            tensor_logits = logits
        else:
            tensor_logits = np.asarray(logits, dtype=float)

        if tensor_logits.ndim == 1:
            tensor_logits = tensor_logits[np.newaxis, :]
            was_1d = True
        else:
            was_1d = False

        batch_size, vocab_size = tensor_logits.shape
        mask = np.zeros((batch_size, vocab_size), dtype=tensor_logits.dtype)
        for token_id in self.forbidden_token_ids:
            if 0 <= token_id < vocab_size:
                mask[:, token_id] = -1e10

        logits_masked = tensor_logits + mask

        if self.audit_trace and self.intercepts_log is not None:
            intercept_record = {
                "iteration": self.intercepts_count,
                "vocab_size": vocab_size,
                "forbidden_count": len(self.forbidden_token_ids),
                "max_logit_before": float(np.max(tensor_logits)),
                "max_logit_after": float(np.max(logits_masked)),
                "min_logit_before": float(np.min(tensor_logits)),
                "min_logit_after": float(np.min(logits_masked)),
            }
            if input_ids is not None and hasattr(input_ids, "shape") and len(input_ids.shape) > 0:
                last_token = input_ids[-1] if len(input_ids) > 0 else -1
                intercept_record["last_token_id"] = int(last_token)
            self.intercepts_log.append(intercept_record)
            self.intercepts_count += 1

        if was_1d:
            logits_masked = logits_masked[0]

        return logits_masked

    def get_audit_log(self) -> Optional[list[Dict]]:
        """Retorna el registro de auditoría de interceptiones."""
        return self.intercepts_log.copy() if self.intercepts_log else None

    def get_statistics(self) -> Dict[str, any]:
        """Retorna estadísticas de funcionamiento."""
        return {
            "logits_processed": self.logits_processed_count,
            "intercepts_total": self.intercepts_count,
            "forbidden_tokens": len(self.forbidden_token_ids),
            "hard_only_mode": self.hard_only,
            "audit_trace_enabled": self.audit_trace is not None,
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

    Mantiene singleton por dispositivo para evitar duplicar estado.
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
        """
        Crea o retorna procesador existente.

        Args:
            w_bank: Matriz de tokens prohibidos
            device_key: Clave para singleton (defecto: "default")
            hard_only: Modo hard-only
            audit_trace: Modo auditoría
            cuda_device: Dispositivo CUDA

        Returns:
            Instancia de DeterministicMUXLogitsProcessor
        """
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
    tokenizer: any,
    embedding_service: Optional[any] = None,
    hard_only: bool = False,
    audit_trace: bool = False,
) -> Tuple[DeterministicMUXLogitsProcessor, Dict]:
    """
    Función de conveniencia para crear procesador desde políticas directamente.

    Compila políticas con InvariantSynthesizer y retorna procesador listo para usar.

    Args:
        policies: Lista de políticas a compilar
        tokenizer: Tokenizador Llama
        embedding_service: Servicio de embeddings (opcional)
        hard_only: Modo hard-only
        audit_trace: Modo auditoría

    Returns:
        Tupla (procesador, reporte_compilación)
    """
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
