# idicoc_core/runtime/guardian.py
from __future__ import annotations
import multiprocessing as mp
import time
from typing import Callable, Any

from idicoc_core.core.pipeline.kernel import CustodialKernel
from idicoc_core.core.custody.merkle_dag import CustodialTraceManager
from idicoc_core.exceptions.integrity_breach import HardHaltException
from idicoc_core.runtime.loader import recover_input_from_snapshot
from idicoc_utils.logger import get_logger


def _run_kernel(kernel_factory: Callable[[], CustodialKernel], raw_input: Any, result_queue: mp.Queue) -> None:
    try:
        kernel = kernel_factory()
        kernel.process(raw_input)
        result_queue.put(("SUCCESS", None))
    except HardHaltException as e:
        result_queue.put(("HARD_HALT", e))
    except Exception as e:
        result_queue.put(("ERROR", e))


class CustodialGuardian:
    """
    CustodialGuardian — Supervisor externo del Kernel.

    Funciones:
    - Detecta Hard Halt (SystemExit)
    - Recupera el último snapshot del CTM
    - Reconstruye el input previo a la divergencia
    - Aplica exponential backoff
    - Relanza el Kernel
    """

    def __init__(
        self,
        kernel_factory: Callable[[], CustodialKernel],
        ctm: CustodialTraceManager,
        max_retries: int = 5
    ):
        self.kernel_factory = kernel_factory
        self.ctm = ctm
        self.max_retries = max_retries
        self.logger = get_logger("guardian")
        self._retry_count = 0

    def run(self, raw_input: Any) -> None:
        """Ciclo de vida supervisado del Kernel."""

        while self._retry_count < self.max_retries:
            try:
                self._verify_system_integrity()

                ctx = mp.get_context("fork")
                result_queue: mp.Queue = ctx.Queue()
                process = ctx.Process(
                    target=_run_kernel,
                    args=(self.kernel_factory, raw_input, result_queue),
                )
                process.start()
                process.join()

                if result_queue.empty():
                    if process.exitcode != 0:
                        raise RuntimeError("Kernel child process failed without a queue result.")
                    self._retry_count = 0
                    return

                status, data = result_queue.get()
                if status == "SUCCESS":
                    self._retry_count = 0
                    return
                if status == "HARD_HALT":
                    raw_input = self._handle_hard_halt(raw_input)
                    continue
                raise data

            except HardHaltException:
                raw_input = self._handle_hard_halt(raw_input)

            except Exception as e:
                self._handle_unexpected_failure(e)

        self.logger.critical("CIRCUIT_BREAKER_OPEN: Entrada segregada permanentemente.")
        raise RuntimeError("CustodialGuardian: Circuit Breaker abierto.")

    def _verify_system_integrity(self) -> None:
        if not self.ctm:
            raise RuntimeError("CTM no inicializado en el Guardian.")

    def _handle_hard_halt(self, input_data: Any) -> Any:
        """Gestiona Hard Halt y reconstruye el input previo."""
        self._retry_count += 1

        root = self.ctm.root_hash

        self.logger.warning(
            "KERNEL_HARD_HALT_DETECTED",
            extra={
                "iiae_data": {
                    "event": "CRITICAL_HALT",
                    "retry_attempt": self._retry_count,
                    "root_hash": root,
                    "remedy": "exponential_backoff + state_recovery"
                }
            }
        )

        # Recuperación del input previo desde el snapshot
        recovered_input = recover_input_from_snapshot(root, self.ctm)

        # Backoff exponencial
        sleep_time = min(2 ** self._retry_count, 30)
        time.sleep(sleep_time)

        return recovered_input

    def _handle_unexpected_failure(self, e: Exception) -> None:
        self._retry_count += 1
        self.logger.error(f"Unexpected Runtime Failure: {str(e)}")
        time.sleep(1)
