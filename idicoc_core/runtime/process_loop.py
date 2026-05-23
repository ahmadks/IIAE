from __future__ import annotations
import signal
import sys
from typing import Callable, Iterable, Any

from idicoc_core.runtime.guardian import CustodialGuardian
from idicoc_core.core.custody.merkle_dag import CustodialTraceManager
from idicoc_core.util.logger import get_logger

class ProcessLoop:
    """
    ProcessLoop — Orchestrator de Alto Nivel.
    
    Responsabilidades:
    - Ciclo de vida del sistema (Graceful Shutdown).
    - Instrumentación y telemetría de flujo.
    - Delegación de resiliencia al CustodialGuardian.
    """

    def __init__(
        self,
        kernel_factory: Callable[[], Any],
        ctm: CustodialTraceManager,
        guardian: CustodialGuardian | None = None,
    ):
        self.ctm = ctm
        self.kernel_factory = kernel_factory
        self.guardian = guardian or CustodialGuardian(kernel_factory, ctm)
        self.logger = get_logger("runtime.process_loop")
        self._running = True
        self._setup_signals()

    def _setup_signals(self) -> None:
        """Registra manejadores para terminación limpia."""
        signal.signal(signal.SIGTERM, self._handle_exit)
        signal.signal(signal.SIGINT, self._handle_exit)

    def _handle_exit(self, signum: int, frame: Any) -> None:
        self.logger.info(f"Signal {signum} recibida. Iniciando cierre ordenado...")
        self._running = False

    def run(self, input_stream: Iterable[Any]) -> None:
        """Ejecuta el bucle principal con monitoreo de estado."""
        self.logger.info("Iniciando IDICOC ProcessLoop.")
        
        try:
            for raw_input in input_stream:
                if not self._running:
                    self.logger.info("Bucle detenido por señal externa.")
                    break
                
                # Ejecución supervisada
                self.guardian.run(raw_input)
                
        except Exception as e:
            self.logger.critical(f"Fallo crítico en ProcessLoop: {str(e)}")
            raise
        
        finally:
            self.logger.info("Pipeline cerrado. Auditoría de estado finalizada.")